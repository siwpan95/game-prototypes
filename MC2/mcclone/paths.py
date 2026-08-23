"""项目路径常量（方案 B 重构后统一数据/存档定位）。

历史：重构前各模块用 ``os.path.dirname(__file__)`` 推导 data/，模块平铺在
example/ 根目录时刚好正确；移入 mcclone/ 分层包后，__file__ 指向包内深层
路径，data/ 会被错定位到 mcclone/.../data。

本模块以 **mcclone 包目录的父目录** 作为项目根（example/），与打包时
build.spec 的 datas=(ROOT/data -> data) 保持一致，运行期/测试期/冻结期均正确。
"""

import os

# mcclone/ 包目录（本文件所在目录）
PACKAGE_DIR: str = os.path.dirname(os.path.abspath(__file__))
# 项目根目录：example/（mcclone 的父目录）
PROJECT_ROOT: str = os.path.dirname(PACKAGE_DIR)
# 数据目录：example/data
DATA_DIR: str = os.path.join(PROJECT_ROOT, "data")
# 存档目录：example/save
SAVE_DIR: str = os.path.join(PROJECT_ROOT, "save")
