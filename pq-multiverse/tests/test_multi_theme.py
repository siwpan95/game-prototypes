"""
多主题测试 - PQ 架构

测试 PQ 核心架构在所有主题下是否正常工作。
"""
import sys
import os

# 添加src目录到路径
src_path = os.path.dirname(os.path.abspath(__file__))
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from themed_engine_pq import PQThemedGameEngine


def test_theme(theme_name: str):
    """测试单个主题"""
    print(f"\n{'='*60}")
    print(f"测试主题: {theme_name}")
    print(f"{'='*60}")
    
    try:
        # 1. 创建引擎
        engine = PQThemedGameEngine(theme_name, seed=12345)
        print(f"  ✅ 引擎创建成功 (主题: {engine.theme.name})")
        
        # 2. 创建角色
        races = engine.get_available_races()
        classes = engine.get_available_classes()
        
        if not races or not classes:
            print(f"  ⚠️ 主题数据不完整 (races={len(races)}, classes={len(classes)})")
            return False
        
        engine.create_character("测试英雄", races[0], classes[0])
        print(f"  ✅ 角色创建成功: {engine.character.name}")
        print(f"  ✅ 第一个任务: {engine.current_action_text}")
        
        # 3. 模拟 150 个 tick (足够完成第一个任务)
        print(f"  📊 模拟 150 个 tick...")
        
        for i in range(150):
            # 手动推进一个 tick
            status = engine._game_tick_manual()
            
            if status is None:
                break
            
            # 每 20 个 tick 显示一次状态
            if i % 20 == 0 and status:
                print(f"    Tick {status['tick_count']}: {status['current_action']} ({status['progress']:.1%})")
        
        # 4. 检查最终状态
        final_status = engine.get_pq_status()
        char_info = final_status.get('character', {})
        print(f"  ✅ 模拟完成")
        print(f"    队列长度: {final_status.get('queue_length', 0)}")
        print(f"    当前行动: {final_status.get('current_action', 'Unknown')}")
        print(f"    角色等级: {char_info.get('level', 'N/A')}")
        print(f"    角色经验: {char_info.get('exp', 'N/A')}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """主函数"""
    print("📊 开始多主题测试 - PQ 架构\n")
    
    # 获取所有主题
    themes = PQThemedGameEngine.list_themes()
    print(f"发现 {len(themes)} 个主题\n")
    
    # 测试每个主题
    success_count = 0
    failed_themes = []
    
    for theme_name in themes:
        try:
            if test_theme(theme_name):
                success_count += 1
            else:
                failed_themes.append(theme_name)
        except Exception as e:
            print(f"  ❌ 主题 {theme_name} 测试失败: {e}")
            failed_themes.append(theme_name)
    
    # 显示测试结果
    print(f"\n{'='*60}")
    print(f"测试结果")
    print(f"{'='*60}")
    print(f"✅ 成功: {success_count}/{len(themes)} 个主题")
    
    if failed_themes:
        print(f"❌ 失败: {len(failed_themes)} 个主题")
        print(f"  失败主题: {', '.join(failed_themes)}")
    else:
        print(f"🎉 所有主题测试通过！")
    
    print(f"\n{'='*60}")


if __name__ == '__main__':
    main()
