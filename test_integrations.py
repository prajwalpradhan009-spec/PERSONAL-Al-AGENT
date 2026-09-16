"""
Integration Layer Tests
Verifies the application capability registry, the (app, capability) tool
resolver, and the no-credential fallback paths of each integration module.

Run: .\\.venv\\Scripts\\python.exe -m unittest test_integrations -v
"""

import unittest
from pathlib import Path

from app.integrations import registry
from app.integrations.dispatcher import execute_tool, get_tool, list_tools, tool_map
from app.integrations import spotify, browser, file_system, app_launcher, youtube, github, google, discord
from app.core import function_calling as fc


class TestRegistry(unittest.TestCase):
    def test_applications_registered(self):
        self.assertIn("spotify", registry.APPLICATIONS)
        self.assertIn("browser", registry.APPLICATIONS)
        self.assertIn("filesystem", registry.APPLICATIONS)
        self.assertIn("windows", registry.APPLICATIONS)
        self.assertIn("app_launcher", registry.APPLICATIONS)
        self.assertIn("youtube", registry.APPLICATIONS)
        self.assertIn("github", registry.APPLICATIONS)
        self.assertIn("google", registry.APPLICATIONS)
        self.assertIn("discord", registry.APPLICATIONS)

    def test_capability_check(self):
        self.assertTrue(registry.has_capability("spotify", "play"))
        self.assertTrue(registry.has_capability("spotify", "current_track"))
        self.assertFalse(registry.has_capability("spotify", "nope"))

    def test_resolve_app_key(self):
        self.assertEqual(registry.resolve_app_key("open youtube"), "youtube")
        self.assertEqual(registry.resolve_app_key("music"), "spotify")

    def test_capability_summary(self):
        text = registry.capability_summary_text()
        self.assertIn("spotify", text)
        self.assertIn("current_track", text)


class TestDispatcher(unittest.TestCase):
    def test_all_registered_tools_resolve(self):
        mapping = tool_map()
        self.assertGreaterEqual(len(mapping), 9)
        for app_key, caps in registry.APPLICATIONS.items():
            for cap in caps["capabilities"]:
                fn = get_tool(app_key, cap)
                self.assertIsNotNone(fn, f"tool missing for {app_key}.{cap}")

    def test_execute_unknown(self):
        res = execute_tool("nope", "x")
        self.assertFalse(res.get("success"))
        res = execute_tool("spotify", "fly_to_moon")
        self.assertFalse(res.get("success"))

    def test_execute_spotify_fallback_open(self):
        # open_spotify requires no credentials (desktop URI fallback uses shell).
        res = spotify.open_spotify()
        self.assertTrue(res.get("success"))

    def test_execute_spotify_volume_no_creds(self):
        res = spotify.set_volume(40)
        self.assertFalse(res.get("success"))
        self.assertIn("Web API", res.get("error", ""))

    def test_execute_github_no_token(self):
        # Public listing works without a token; creating a repo needs authentication.
        res = github.create_repo("agent_auto_should_fail")
        self.assertFalse(res.get("success"))
        self.assertIn("token", (res.get("error") or "").lower())

    def test_youtube_browser_fallback(self):
        res = youtube.search_open_browser("python tutorial")
        self.assertTrue(res.get("success"))

    def test_google_no_creds(self):
        res = google.search_drive("resume")
        self.assertFalse(res.get("success"))

    def test_discord_no_token(self):
        res = discord.get_bot_info()
        self.assertFalse(res.get("success"))


class TestFileSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(file_system.WORKSPACE_DIR) / "_test_fs"
        cls.tmp.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        import shutil
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_create_read_file(self):
        p = self.tmp / "notes.txt"
        res = file_system.create_file(str(p), "hello world")
        self.assertTrue(res.get("success"))
        res = file_system.read_file(str(p))
        self.assertTrue(res.get("success"))
        self.assertIn("hello world", res["content"])

    def test_search_files(self):
        file_system.create_file(str(self.tmp / "report.pdf"), "x")
        res = file_system.search_files("*.pdf", directory=str(self.tmp))
        self.assertTrue(res.get("success"))
        self.assertGreaterEqual(res["count"], 1)

    def test_delete_requires_confirmation(self):
        p = self.tmp / "keep.txt"
        file_system.create_file(str(p), "keep me")
        res = file_system.delete_file(str(p))
        self.assertFalse(res.get("success"))
        self.assertTrue(p.exists())
        res = file_system.delete_file(str(p), confirm=True)
        self.assertTrue(res.get("success"))
        self.assertFalse(p.exists())

    def test_create_csv(self):
        p = self.tmp / "data.csv"
        res = file_system.create_csv(str(p), [["a", "b"], ["1", "2"]], headers=["x", "y"])
        self.assertTrue(res.get("success"))
        rd = file_system.read_csv(str(p))
        self.assertEqual(rd["rows"][0], ["x", "y"])

    def test_convert_json_to_csv(self):
        p = self.tmp / "data.json"
        p.write_text('[{"name": "Prajjwal", "role": "Founder"}]', encoding="utf-8")
        res = file_system.convert_file(str(p), "csv")
        self.assertTrue(res.get("success"))
        self.assertTrue(Path(res["to_path"]).exists())

    def test_move_rename(self):
        src = self.tmp / "moved.txt"
        src.write_text("x", encoding="utf-8")
        res = file_system.move_file(str(src), str(self.tmp / "moved2.txt"))
        self.assertTrue(res.get("success"))
        res = file_system.rename_file(str(self.tmp / "moved2.txt"), "final.txt")
        self.assertTrue(res.get("success"))
        self.assertTrue((self.tmp / "final.txt").exists())


class TestFunctionCallingPath(unittest.TestCase):
    def test_capability_prompt_builds(self):
        prompt = fc.build_system_function_calling_prompt()
        self.assertIn("AVAILABLE APPLICATIONS & CAPABILITIES", prompt)
        self.assertIn("spotify", prompt)
        self.assertIn('"action": "tool"', prompt)

    def test_fallback_extracts_spotify_play(self):
        payload = fc.fallback_intent_extractor("Play Believer by Imagine Dragons")
        self.assertIn(payload["action"], ("spotify_play", "spotify_playlist"))

    def test_fallback_volume(self):
        payload = fc.fallback_intent_extractor("Set volume to 40 percent")
        self.assertEqual(payload["action"], "set_volume")
        self.assertEqual(payload["level"], 40)

    def test_fallback_youtube(self):
        payload = fc.fallback_intent_extractor("Search Python DSA tutorial on YouTube")
        self.assertEqual(payload["action"], "youtube_search")

    def test_dispatch_tool_action_passthrough(self):
        # spotify.open executes via URI fallback (no creds needed)
        spoken, actions = fc.execute_structured_action(
            {"action": "tool", "app": "spotify", "capability": "open", "params": {}, "response": "ok"}
        )
        self.assertEqual(spoken, "ok")
        self.assertEqual(actions[0]["status"], "success")


if __name__ == "__main__":
    unittest.main()