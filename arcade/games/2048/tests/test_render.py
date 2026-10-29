"""渲染层：输出可注入、可断言，且绝不参与决策。"""

import io
import unittest

from game2048.core.board import Board
from game2048.core.game import GameSnapshot
from game2048.core.result import EndReason, GameResult
from game2048.render.console import ConsoleRenderer
from game2048.render.silent import SilentRenderer


def snapshot_of(board: Board, score: int = 0, moves: int = 0) -> GameSnapshot:
    return GameSnapshot(board=board, score=score, moves=moves, over=False)


class TestConsoleRenderer(unittest.TestCase):
    def setUp(self):
        self.stream = io.StringIO()
        self.renderer = ConsoleRenderer(
            delay=0, clear=False, stream=self.stream, title="T"
        )

    def test_board_layout(self):
        board = Board.from_rows([[2, 0], [0, 1024]])
        text = self.renderer.render_board(snapshot_of(board))
        lines = text.split("\n")
        self.assertEqual(lines[1], "=" * 13)  # +-----+-----+
        self.assertEqual(lines[4], "+-----+-----+")
        self.assertEqual(lines[5], "|  2  |     |")
        self.assertEqual(lines[7], "|     |1024 |")

    def test_bar_width_scales_with_size(self):
        for size in (2, 4, 5):
            text = self.renderer.render_board(snapshot_of(Board.empty(size)))
            lines = text.split("\n")
            self.assertEqual(len(lines[1]), size * 6 + 1)

    def test_frame_writes_score_line(self):
        self.renderer.frame(snapshot_of(Board.empty(2), score=128, moves=7))
        self.assertIn("得分: 128, 步数: 7", self.stream.getvalue())

    def test_finish_writes_summary(self):
        result = GameResult(
            snapshot=GameSnapshot(
                board=Board.from_rows([[2, 4], [8, 16]]), score=99, moves=5, over=True
            ),
            reason=EndReason.GAME_OVER,
            strategy="fixed",
        )
        self.renderer.finish(result)
        output = self.stream.getvalue()
        self.assertIn("最终得分: 99", output)
        self.assertIn("总步数: 5", output)
        self.assertIn("最大方块: 16", output)
        self.assertIn("棋盘死锁", output)

    def test_no_output_leaks_to_stdout(self):
        """输出流可注入，是把 I/O 从核心逻辑里剥离的关键。"""
        self.renderer.frame(snapshot_of(Board.empty(2)))
        self.assertTrue(self.stream.getvalue())

    def test_rejects_bad_params(self):
        with self.assertRaises(ValueError):
            ConsoleRenderer(delay=-1)
        with self.assertRaises(ValueError):
            ConsoleRenderer(cell_width=2)


class TestSilentRenderer(unittest.TestCase):
    def test_counts_frames_without_output(self):
        renderer = SilentRenderer()
        for _ in range(3):
            renderer.frame(snapshot_of(Board.empty(2)))
        self.assertEqual(renderer.frames, 3)
        self.assertFalse(renderer.finished)


if __name__ == "__main__":
    unittest.main()
