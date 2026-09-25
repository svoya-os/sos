# SPDX-License-Identifier: Apache-2.0
import datetime as dt
import unittest

from jackson.config import MemoryConfig
from jackson.memory import Memory, fts_query, split_frontmatter, touch_frontmatter
from jackson.paths import Paths
from jackson.skills import Skills
from jackson.tools.base import T1, T2
from tests.fakes import make_app, rmtree, short_tmpdir
from tests.test_permissions import ctx_for


class MemoryTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.paths = Paths.for_root(self.root)
        self.mem = Memory(self.paths, MemoryConfig(git=False), lang="ru")
        self.mem.ensure()

    def tearDown(self):
        rmtree(self.root)

    def test_files_are_plain_markdown(self):
        self.assertTrue((self.paths.memory_dir / "USER.md").read_text(encoding="utf-8").startswith("# Обо мне"))
        self.assertTrue((self.paths.memory_dir / "MEMORY.md").exists())
        self.assertTrue((self.paths.memory_dir / "journal").is_dir())

    def test_remember_search_ru_morphology(self):
        self.mem.remember("У пользователя видеокарта RTX 4090 на 24 ГБ", "user", dt.date(2026, 9, 24))
        self.mem.remember("Датасеты лежат в /srv/ai/datasets", today=dt.date(2026, 9, 24))
        self.mem.remember("Likes dark themes and IBM Plex fonts")
        hits = self.mem.search("какая у меня видеокарту?")
        self.assertTrue(hits and "RTX 4090" in hits[0].text)
        self.assertEqual(hits[0].file, "USER.md")
        self.assertIn("/srv/ai/datasets", self.mem.search("где мои датасеты")[0].text)
        self.assertIn("dark themes", self.mem.search("theme")[0].text)
        self.assertEqual(self.mem.search("совершенно другое"), [])

    def test_duplicate_is_not_written_twice(self):
        first = self.mem.remember("любит кофе без сахара")
        second = self.mem.remember("любит кофе без сахара")
        self.assertTrue(first.lines)
        self.assertEqual(second.lines, [])

    def test_relevant_block(self):
        self.mem.remember("Зовут Лёша", "user")
        self.mem.remember("Проект SOS собирается командой make iso")
        block = self.mem.relevant("как собрать iso?")
        self.assertIn("Зовут Лёша", block)
        self.assertIn("make iso", block)

    def test_forget_and_undo(self):
        c = self.mem.remember("пароль от wifi на холодильнике")
        changes = self.mem.forget("холодильник")
        self.assertEqual(len(changes), 1)
        self.assertNotIn("холодильник", self.mem.read("MEMORY.md"))
        self.assertEqual(self.mem.search("холодильник"), [])
        self.mem.restore(changes[0].file, changes[0].prev_sha256, changes[0].new_sha256)
        self.assertIn("холодильник", self.mem.read("MEMORY.md"))
        self.assertTrue(c.lines)

    def test_journal(self):
        when = dt.datetime(2026, 9, 25, 18, 42)
        change = self.mem.journal("открыл Firefox (a-123)", when)
        self.assertEqual(change.file, "journal/2026-09-25.md")
        text = self.mem.read("journal/2026-09-25.md")
        self.assertIn("# 2026-09-25", text)
        self.assertIn("- 18:42 · открыл Firefox (a-123)", text)

    def test_fts_query_is_safe(self):
        q = fts_query('drop "table"; OR -- :-) видеокарту*')
        self.assertNotIn(';', q.replace('" OR "', ""))
        self.assertIsNone(fts_query("и в на"))


class ObsidianTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        self.app = make_app(self.root, extra={"memory": {"dir": "~/Obsidian/SOS"}})
        home = self.app.paths.home
        self.vault = home / "Obsidian"
        (self.vault / ".obsidian").mkdir(parents=True)
        (self.vault / "Projects").mkdir()
        (self.vault / "Projects" / "Plan.md").write_text("---\naliases: [plan]\n---\n# План\n\nСобрать ISO к пятнице.\n",
                                                        encoding="utf-8")
        (self.vault / "Daily.md").write_text("Встреча с Олей про датасеты.\n", encoding="utf-8")
        # rebuild with the vault in place
        self.app = make_app(self.root, extra={"memory": {"dir": "~/Obsidian/SOS"}})
        self.mem = self.app.memory
        self.mem.ensure()
        self.ctx = ctx_for(self.app, home)

    def tearDown(self):
        rmtree(self.root)

    def test_vault_detection_and_frontmatter(self):
        self.assertTrue(self.mem.obsidian)
        self.assertEqual(self.mem.vault, self.vault.resolve())
        self.assertEqual(self.mem.dir, self.app.paths.home / "Obsidian" / "SOS")
        user = (self.mem.dir / "USER.md").read_text(encoding="utf-8")
        items, body = split_frontmatter(user)
        keys = [k for k, _ in items]
        self.assertEqual(keys[:2], ["created", "updated"])
        self.assertIn("tags", keys)
        self.assertNotIn("<!--", user)
        self.mem.remember("любит тёмную тему", "user")
        items2, _ = split_frontmatter((self.mem.dir / "USER.md").read_text(encoding="utf-8"))
        self.assertEqual(dict(items2)["created"], dict(items)["created"])
        self.assertFalse((self.mem.dir / ".git").exists())  # never nest a repo in a vault

    def test_vault_root_uses_jackson_subfolder(self):
        app = make_app(self.root, extra={"memory": {"dir": "~/Obsidian"}})
        self.assertEqual(app.memory.dir, self.vault / "Jackson")

    def test_notes_search_and_read_whole_vault(self):
        hits = self.app.registry.get("notes.search").fn(self.ctx, {"query": "датасеты"})
        self.assertIn("Daily.md", hits.content)
        plan = self.app.registry.get("notes.read").fn(self.ctx, {"note": "[[Plan]]"})
        self.assertTrue(plan.ok)
        self.assertIn("Собрать ISO", plan.content)
        self.assertFalse(self.app.registry.get("notes.read").fn(self.ctx, {"note": "../../etc/passwd"}).ok)

    def test_writes_inside_jackson_folder_are_t1_elsewhere_t2(self):
        write = self.app.registry.get("notes.write")
        inside = write.assessment(self.ctx, {"note": "Идеи", "content": "- [[Plan]] ускорить\n"})
        self.assertEqual(inside.tier, T1)
        outside = write.assessment(self.ctx, {"note": "Projects/Plan.md", "content": "новый план"})
        self.assertEqual(outside.tier, T2)
        self.assertTrue(outside.reasons)
        fs_out = self.app.registry.get("fs.write").assessment(
            self.ctx, {"path": str(self.vault / "Daily.md"), "content": "x"})
        self.assertEqual(fs_out.tier, T2)  # the vault guard also covers generic file tools

    def test_write_note_is_obsidian_friendly_and_undoable(self):
        res = self.app.registry.get("notes.write").fn(self.ctx, {"note": "Идеи", "content": "# Идеи\n\n- см. [[Plan]]\n",
                                                                  "tags": ["ideas"]})
        self.assertTrue(res.ok and res.verified)
        path = self.mem.dir / "Идеи.md"
        items, body = split_frontmatter(path.read_text(encoding="utf-8"))
        self.assertIn("[jackson, ideas]", dict(items)["tags"])
        self.assertIn("[[Plan]]", body)
        ids = [self.app.undo.register(s).id for s in res.undo]
        self.assertTrue(self.app.undo.undo(ids[0], "ru").ok)
        self.assertFalse(path.exists())
        # overwriting a user's note keeps its own front matter
        res2 = self.app.registry.get("notes.write").fn(self.ctx, {"note": "Projects/Plan.md", "content": "# План v2\n"})
        text = (self.vault / "Projects" / "Plan.md").read_text(encoding="utf-8")
        self.assertIn("aliases: [plan]", text)
        self.assertIn("# План v2", text)
        self.assertTrue(res2.undo)

    def test_touch_frontmatter_preserves_keys(self):
        text = touch_frontmatter("---\ntitle: X\ntags:\n  - a\n---\nbody\n", ["jackson"])
        items, body = split_frontmatter(text)
        self.assertEqual([k for k, _ in items], ["created", "updated", "title", "tags"])
        self.assertIn("- a", dict(items)["tags"])
        self.assertEqual(body, "body\n")


class SkillsTest(unittest.TestCase):
    def setUp(self):
        self.root = short_tmpdir()
        d = self.root / "skills" / "video-render"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("---\nname: video-render\ndescription: Render short videos with ComfyUI "
                                    "and Wan models\n---\n# Steps\n1. Check VRAM\n", encoding="utf-8")

    def tearDown(self):
        rmtree(self.root)

    def test_catalogue_and_relevance(self):
        skills = Skills(self.root / "skills")
        self.assertEqual(skills.load()[0].name, "video-render")
        self.assertEqual(skills.relevant("render a short video with wan")[0].name, "video-render")
        self.assertEqual(skills.relevant("какая погода"), [])
        block = skills.prompt_block("render video with comfyui", "en")
        self.assertIn("grant no permissions", block)
        self.assertIn("Check VRAM", block)


if __name__ == "__main__":
    unittest.main()
