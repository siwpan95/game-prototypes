"""冒烟测试：按地图分组遇敌（T1.3 验收）

覆盖：荒野只刷区域1敌人、遗迹只刷区域5敌人、空区域回退荒野通用怪。
"""
import os
import shutil
import sys
import tempfile

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from data import ConfigLoader  # noqa: E402


def main():
    tmp_dir = tempfile.mkdtemp(prefix="maga_enemytest_")
    try:
        config_path = os.path.join(tmp_dir, "config.xlsx")
        shutil.copy(os.path.join(REPO_ROOT, "config.xlsx"), config_path)
        config = ConfigLoader(config_path)
        assert config.load_all(), "配置加载失败"

        # 区域分组正确加载
        regions = {eid: e.region_id for eid, e in config.enemies.items()}
        assert regions[1] == 1 and regions[5] == 1, "荒野怪区域错误"
        assert regions[4] == 5 and regions[8] == 5, "遗迹怪区域错误"

        # 荒野（地图1）只会遇到区域 1 的敌人
        wilderness_names = {config.enemies[i].name for i in (1, 2, 3, 5)}
        for _ in range(200):
            enemy = config.get_random_enemy(1)
            assert enemy is not None and enemy.name in wilderness_names, \
                f"荒野遇到了非本区域敌人: {enemy.name if enemy else None}"

        # 地下遗迹（地图5）只会遇到区域 5 的敌人
        ruin_names = {config.enemies[i].name for i in (4, 6, 7, 8)}
        for _ in range(200):
            enemy = config.get_random_enemy(5)
            assert enemy is not None and enemy.name in ruin_names, \
                f"遗迹遇到了非本区域敌人: {enemy.name if enemy else None}"

        # 未配置敌人的区域回退荒野通用怪
        for _ in range(50):
            enemy = config.get_random_enemy(99)
            assert enemy is not None and enemy.name in wilderness_names, \
                f"空区域应回退荒野怪: {enemy.name if enemy else None}"

        print("SMOKE OK: 遭遇表按地图分组全部断言通过")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
