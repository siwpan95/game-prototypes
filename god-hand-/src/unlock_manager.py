import json
import os


class UnlockManager:
    def __init__(self,
                 save_path: str = 'data/unlocks.json',
                 data_path: str = 'data'):
        """
        save_path : 可写的存档文件路径（exe 同级目录下）
        data_path : 只读数据目录（兼容 _MEIPASS）
        """
        self.path = save_path
        self.data_path = data_path

        if not os.path.exists(self.path):
            self.data = {
                "endings_seen": [],
                "characters_unlocked": ["heracles"],
                "meta_upgrades": []
            }
            self.save()
        else:
            with open(self.path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)

    def save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def unlock_ending(self, ending_id: str):
        if ending_id not in self.data['endings_seen']:
            self.data['endings_seen'].append(ending_id)
            # 自动解锁角色
            if ending_id == 'ending_glory_death' and 'beowulf' not in self.data['characters_unlocked']:
                self.data['characters_unlocked'].append('beowulf')
            if ending_id == 'ending_destroyer' and 'kratos' not in self.data['characters_unlocked']:
                self.data['characters_unlocked'].append('kratos')
            self.save()

    def get_available_characters(self) -> list:
        return self.data['characters_unlocked']

    def is_unlocked(self, feature: str) -> bool:
        n = len(self.data['endings_seen'])
        if feature == 'hidden_labours':
            return n >= 5
        if feature == 'chaos_mode':
            return n >= 10
        if feature == 'challenge_mode':
            return n >= 1
        if feature == 'god_eye':
            return n >= 3
        if feature == 'fate_thread':
            return n >= 5
        return False

    def get_unlocked_upgrades(self) -> list:
        """返回已解锁的代币列表（用于UI展示）"""
        return [u for u in ('challenge_mode', 'god_eye', 'fate_thread')
                if self.is_unlocked(u)]

    def upgrade_name(self, upgrade_id: str) -> str:
        names = {
            'challenge_mode': '挑战模式',
            'god_eye': '神之视角',
            'fate_thread': '命运织线',
        }
        return names.get(upgrade_id, upgrade_id)
