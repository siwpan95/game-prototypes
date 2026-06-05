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
        if feature == 'hidden_labours':
            return len(self.data['endings_seen']) >= 5
        if feature == 'chaos_mode':
            return len(self.data['endings_seen']) >= 10
        return False
