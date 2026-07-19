#include <librealsense2/rs.hpp>
#include <turbojpeg.h>

#include <arpa/inet.h>
#include <poll.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/un.h>
#include <unistd.h>

#include <array>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <csignal>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <stdexcept>
#include <string>

namespace {

constexpr std::size_t kHeaderSize = 28;
constexpr std::uint8_t kProtocolVersion = 1;
constexpr unsigned int kFrameTimeoutMs = 5000;
std::atomic<bool> running{true};

struct Options {
    std::string socket_path = "/tmp/dex-realsense-rgb.sock";
    std::string serial;
    int width = 1280;
    int height = 720;
    int fps = 30;
    int jpeg_quality = 82;
};

void print_help() {
    std::cout
        << "RealSense RGB bridge\n\n"
        << "Usage: realsense_rgb_bridge [options]\n"
        << "  --socket PATH         Unix socket path\n"
        << "  --serial SERIAL       Optional RealSense serial\n"
        << "  --width N             Color width (default 1280)\n"
        << "  --height N            Color height (default 720)\n"
        << "  --fps N               Color FPS (default 30)\n"
        << "  --jpeg-quality N      JPEG quality 1-100 (default 82)\n"
        << "  --help                Show this help\n";
}

int parse_positive(const std::string& value, const char* name) {
    std::size_t consumed = 0;
    int result = 0;
    try {
        result = std::stoi(value, &consumed);
    } catch (const std::exception&) {
        throw std::runtime_error(std::string(name) + " must be an integer");
    }
    if (consumed != value.size() || result <= 0) {
        throw std::runtime_error(std::string(name) + " must be positive");
    }
    return result;
}

Options parse_options(int argc, char** argv) {
    Options options;
    for (int index = 1; index < argc; ++index) {
        const std::string argument = argv[index];
        if (argument == "--help") {
            print_help();
            std::exit(0);
        }
        if (index + 1 >= argc) {
            throw std::runtime_error("Missing value for " + argument);
        }
        const std::string value = argv[++index];
        if (argument == "--socket") {
            options.socket_path = value;
        } else if (argument == "--serial") {
            options.serial = value;
        } else if (argument == "--width") {
            options.width = parse_positive(value, "width");
        } else if (argument == "--height") {
            options.height = parse_positive(value, "height");
        } else if (argument == "--fps") {
            options.fps = parse_positive(value, "fps");
        } else if (argument == "--jpeg-quality") {
            options.jpeg_quality = parse_positive(value, "jpeg-quality");
        } else {
            throw std::runtime_error("Unknown option: " + argument);
        }
    }
    if (options.jpeg_quality > 100) {
        throw std::runtime_error("jpeg-quality must be between 1 and 100");
    }
    if (options.socket_path.empty()) {
        throw std::runtime_error("socket path cannot be empty");
    }
    if (options.socket_path.size() >= sizeof(sockaddr_un::sun_path)) {
        throw std::runtime_error("socket path is too long");
    }
    return options;
}

std::uint64_t host_to_big64(std::uint64_t value) {
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
    return __builtin_bswap64(value);
#else
    return value;
#endif
}

std::array<std::uint8_t, kHeaderSize> make_header(
    std::uint64_t sequence,
    std::uint64_t captured_ns,
    std::uint32_t payload_size
) {
    std::array<std::uint8_t, kHeaderSize> header{};
    std::memcpy(header.data(), "DRGB", 4);
    header[4] = kProtocolVersion;
    const auto sequence_be = host_to_big64(sequence);
    const auto captured_be = host_to_big64(captured_ns);
    const auto size_be = htonl(payload_size);
    std::memcpy(header.data() + 8, &sequence_be, sizeof(sequence_be));
    std::memcpy(header.data() + 16, &captured_be, sizeof(captured_be));
    std::memcpy(header.data() + 24, &size_be, sizeof(size_be));
    return header;
}

bool write_all(int descriptor, const void* data, std::size_t size) {
    const auto* bytes = static_cast<const std::uint8_t*>(data);
    std::size_t written = 0;
    while (written < size && running.load()) {
        const auto result = ::send(descriptor, bytes + written, size - written, 0);
        if (result > 0) {
            written += static_cast<std::size_t>(result);
            continue;
        }
        if (result < 0 && errno == EINTR) {
            continue;
        }
        return false;
    }
    return written == size;
}

uid_t environment_id(const char* name, uid_t fallback) {
    const char* value = std::getenv(name);
    if (value == nullptr || *value == '\0') {
        return fallback;
    }
    char* end = nullptr;
    const auto parsed = std::strtoul(value, &end, 10);
    if (end == nullptr || *end != '\0') {
        throw std::runtime_error(std::string("Invalid ") + name);
    }
    return static_cast<uid_t>(parsed);
}

class SocketFile {
public:
    explicit SocketFile(std::string path) : path_(std::move(path)) {}
    ~SocketFile() { ::unlink(path_.c_str()); }
    SocketFile(const SocketFile&) = delete;
    SocketFile& operator=(const SocketFile&) = delete;

private:
    std::string path_;
};

int create_server(const std::string& path) {
    struct stat status {};
    if (::lstat(path.c_str(), &status) == 0) {
        if (!S_ISSOCK(status.st_mode)) {
            throw std::runtime_error("Refusing to replace non-socket path: " + path);
        }
        if (::unlink(path.c_str()) != 0) {
            throw std::runtime_error("Could not remove stale socket: " + path);
        }
    }

    const int descriptor = ::socket(AF_UNIX, SOCK_STREAM, 0);
    if (descriptor < 0) {
        throw std::runtime_error("Could not create Unix socket");
    }
    sockaddr_un address{};
    address.sun_family = AF_UNIX;
    std::strncpy(address.sun_path, path.c_str(), sizeof(address.sun_path) - 1);
    if (::bind(descriptor, reinterpret_cast<sockaddr*>(&address), sizeof(address)) != 0) {
        const std::string message = std::strerror(errno);
        ::close(descriptor);
        throw std::runtime_error("Could not bind Unix socket: " + message);
    }
    const uid_t owner = environment_id("SUDO_UID", ::getuid());
    const gid_t group = static_cast<gid_t>(environment_id("SUDO_GID", ::getgid()));
    if (::chown(path.c_str(), owner, group) != 0 || ::chmod(path.c_str(), 0600) != 0) {
        const std::string message = std::strerror(errno);
        ::close(descriptor);
        ::unlink(path.c_str());
        throw std::runtime_error("Could not secure Unix socket: " + message);
    }
    if (::listen(descriptor, 1) != 0) {
        const std::string message = std::strerror(errno);
        ::close(descriptor);
        ::unlink(path.c_str());
        throw std::runtime_error("Could not listen on Unix socket: " + message);
    }
    return descriptor;
}

int wait_for_client(int server) {
    pollfd descriptor{server, POLLIN, 0};
    while (running.load()) {
        const int result = ::poll(&descriptor, 1, 250);
        if (result > 0 && (descriptor.revents & POLLIN) != 0) {
            const int client = ::accept(server, nullptr, nullptr);
            if (client >= 0) {
#ifdef SO_NOSIGPIPE
                int enabled = 1;
                ::setsockopt(client, SOL_SOCKET, SO_NOSIGPIPE, &enabled, sizeof(enabled));
#endif
                return client;
            }
        } else if (result < 0 && errno != EINTR) {
            throw std::runtime_error("Unix socket poll failed");
        }
    }
    return -1;
}

void handle_signal(int) { running.store(false); }

}  // namespace

int main(int argc, char** argv) {
    try {
        const Options options = parse_options(argc, argv);
        std::signal(SIGINT, handle_signal);
        std::signal(SIGTERM, handle_signal);
        std::signal(SIGPIPE, SIG_IGN);

        rs2::pipeline pipeline;
        rs2::config configuration;
        if (!options.serial.empty()) {
            configuration.enable_device(options.serial);
        }
        configuration.enable_stream(
            RS2_STREAM_COLOR,
            options.width,
            options.height,
            RS2_FORMAT_BGR8,
            options.fps
        );
        const auto profile = pipeline.start(configuration);
        const auto device = profile.get_device();
        std::cerr << "D435 RGB ready: "
                  << device.get_info(RS2_CAMERA_INFO_NAME) << "\n";

        const int server = create_server(options.socket_path);
        SocketFile socket_file(options.socket_path);
        tjhandle compressor = tjInitCompress();
        if (compressor == nullptr) {
            ::close(server);
            throw std::runtime_error("Could not initialize turbojpeg compressor");
        }

        std::uint64_t sequence = 0;
        while (running.load()) {
            const int client = wait_for_client(server);
            if (client < 0) {
                break;
            }
            while (running.load()) {
                rs2::frameset frames;
                try {
                    frames = pipeline.wait_for_frames(kFrameTimeoutMs);
                } catch (const rs2::error& error) {
                    const std::string message = error.what();
                    if (
                        running.load() &&
                        message.find("Frame didn't arrive") != std::string::npos
                    ) {
                        std::cerr
                            << "D435 RGB frame timeout; keeping stream alive and retrying\n";
                        continue;
                    }
                    throw;
                }
                const rs2::video_frame color = frames.get_color_frame();
                if (!color) {
                    continue;
                }
                unsigned char* jpeg = nullptr;
                unsigned long jpeg_size = 0;
                const int compressed = tjCompress2(
                    compressor,
                    static_cast<const unsigned char*>(color.get_data()),
                    color.get_width(),
                    color.get_stride_in_bytes(),
                    color.get_height(),
                    TJPF_BGR,
                    &jpeg,
                    &jpeg_size,
                    TJSAMP_420,
                    options.jpeg_quality,
                    TJFLAG_FASTDCT
                );
                if (compressed != 0) {
                    const std::string message = tjGetErrorStr2(compressor);
                    tjFree(jpeg);
                    ::close(client);
                    tjDestroy(compressor);
                    ::close(server);
                    throw std::runtime_error(message);
                }
                const auto now = std::chrono::system_clock::now().time_since_epoch();
                const auto captured_ns = static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(now).count()
                );
                const auto header = make_header(
                    ++sequence,
                    captured_ns,
                    static_cast<std::uint32_t>(jpeg_size)
                );
                const bool sent = write_all(client, header.data(), header.size()) &&
                                  write_all(client, jpeg, jpeg_size);
                tjFree(jpeg);
                if (!sent) {
                    break;
                }
            }
            ::close(client);
        }

        tjDestroy(compressor);
        ::close(server);
        pipeline.stop();
        return 0;
    } catch (const std::exception& error) {
        std::cerr << "RealSense RGB bridge failed: " << error.what() << "\n";
        return 2;
    }
}
