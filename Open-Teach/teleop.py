import hydra
from openteach.components import TeleOperator

@hydra.main(version_base = '1.2', config_path = 'configs', config_name = 'teleop')
def main(configs):
    teleop = TeleOperator(configs)
    processes = teleop.get_processes()

    for process in processes:
        process.start()

    try:
        for process in processes:
            process.join()
    except KeyboardInterrupt:
        for process in processes:
            process.join(timeout=2)
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join()

if __name__ == '__main__':
    main()
