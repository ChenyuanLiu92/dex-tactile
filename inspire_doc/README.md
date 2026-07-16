# Inspire 灵巧手资料索引

当前资料主要来自因时机器人第四代 FTP 触觉灵巧手官方参考文件，按用途归档在 `inspire_hand/` 下。

## 目录结构

- `inspire_hand/01_用户手册/`
  - 压阻式触觉用户手册
  - 电容式触觉用户手册
- `inspire_hand/02_参数表/`
  - 压阻式 FTP 触觉手参数表
  - 电容式 FTP 触觉手参数表
- `inspire_hand/03_机械图纸/`
  - `尺寸图/`: 左手、右手尺寸图 PDF
  - `数模_STEP/`: 左手、右手 STEP 数模文件
- `inspire_hand/04_URDF模型/`
  - `left_ftp_ros1/`: 左手 FTP URDF ROS1 包
  - `right_ftp_ros1/`: 右手 FTP URDF ROS1 包
  - `standalone_urdf/`: 单独右手 URDF 文件
- `inspire_hand/05_软件示例/`
  - `ros1_2024-10-25/`: 官方 ROS1 示例
  - `ros2_2024-10-25/`: 官方 ROS2 示例
  - `python_2024-10-25/`: 官方 Python 示例

## 维护约定

- 官方压缩包解压后不再保留压缩包，避免重复占用空间。
- 官方 SDK 或 ROS 包内部结构保持原样，只调整外层分类目录。
- 新增资料优先按用途归入已有一级分类；如果资料类型明显不同，再新增同级分类。
