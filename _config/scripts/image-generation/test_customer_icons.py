"""Offline checks for customer portrait generation and source-reference updates.

Run with: python3 -B -m unittest discover -s _config/scripts/image-generation -p 'test_*.py'
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

import generate_customer_icons_gemini_nanobanana_api as portraits
import generate_missing_domain_icons_gemini_nanobanana_api as domain_icons


PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jS1kAAAAASUVORK5CYII="
)


class CustomerIconTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="productscape-customer-icons-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.output = io.StringIO()
        output_context = contextlib.redirect_stdout(self.output)
        output_context.__enter__()
        self.addCleanup(output_context.__exit__, None, None, None)
        self.path = self.make_domain("alpha")
        self.args = argparse.Namespace(
            domain=None, customer=None, limit=0, model=portraits.DEFAULT_MODEL,
            dry_run=False, json_only=False, skip_existing=False, overwrite=False,
            api_key_env="GEMINI_API_KEY", max_retries=1, retry_delay_seconds=0,
            sleep_seconds=0, skip_customer_icons=False,
        )

    def make_domain(self, domain):
        path = self.root / "example-group" / domain / "customers" / "customers.json"
        path.parent.mkdir(parents=True)
        payload = [{"group": "Mobility", "customers": [
            {
                "id": "driver", "name": "Driver", "icon": "customer.png",
                "description": "Earns income by driving passengers.",
                "careAbout": ["Productive time online"],
                "jobsToBeDone": [{"id": "serve", "name": "Serve trips", "outcome": "Reliable earnings"}],
                "media": [{"type": "video", "src": "intro.mp4"}],
                "kpiPyramids": {"customerOutcomes": {"top": {
                    "id": "wait", "name": "Pickup wait", "icon": "kpi-driver-wait.png",
                }}},
            },
            {"id": "rider", "name": "Rider", "icon": "customer.png"},
        ]}]
        path.write_text(json.dumps(payload), encoding="utf-8")
        (path.parent / "icons").mkdir()
        (path.parent / "icons" / "customer.png").write_bytes(PNG_BYTES)
        (path.parent / "relations.json").write_text(json.dumps({"relations": [
            {"from": "driver", "to": "rider", "name": "Serves trips", "description": "Collects passengers."},
        ]}), encoding="utf-8")
        return path

    def customers(self, path=None):
        return json.loads((path or self.path).read_text())[0]["customers"]

    def snapshot(self):
        return {str(path.relative_to(self.root)): path.read_bytes() for path in self.root.rglob("*") if path.is_file()}

    def fake_image(self, *_):
        return portraits.GeneratedImage(PNG_BYTES, "png")

    def test_upgrades_shared_icons_preserves_content_and_is_idempotent(self):
        original = self.customers()
        with patch.object(portraits, "call_gemini_nanobanana_api", side_effect=self.fake_image) as api:
            self.assertEqual(portraits.generate_icons_for_file(self.path, self.args, "test-key"), (2, True))
            self.assertEqual(api.call_count, 2)
            prompt = api.call_args_list[0].args[1].prompt
            for detail in ("Mobility", "Earns income", "Productive time online", "Reliable earnings", "Collects passengers"):
                self.assertIn(detail, prompt)
            before_rerun = self.snapshot()
            self.assertEqual(portraits.generate_icons_for_file(self.path, self.args, "test-key"), (0, False))
            self.assertEqual(api.call_count, 2)
            self.assertEqual(before_rerun, self.snapshot())
        customers = self.customers()
        self.assertNotEqual(customers[0]["icon"], customers[1]["icon"])
        for before, after in zip(original, customers):
            self.assertEqual({k: v for k, v in before.items() if k != "icon"},
                             {k: v for k, v in after.items() if k != "icon"})
            self.assertEqual((self.path.parent / "icons" / after["icon"]).read_bytes(), PNG_BYTES)
        self.assertEqual((self.path.parent / "icons/customer.png").read_bytes(), PNG_BYTES)

    def test_dry_run_has_no_api_calls_or_filesystem_changes(self):
        self.args.dry_run = True
        self.args.limit = 1
        before = self.snapshot()
        with patch.object(portraits, "call_gemini_nanobanana_api") as api:
            self.assertEqual(portraits.generate_icons_for_file(self.path, self.args, ""), (1, True))
            api.assert_not_called()
        self.assertEqual(before, self.snapshot())

    def test_json_only_links_an_existing_alternate_format_and_leaves_missing_icons(self):
        self.args.json_only = True
        icon_path = self.path.parent / "icons/customer-driver-portrait.webp"
        icon_path.write_bytes(b"existing webp image")
        with patch.object(portraits, "call_gemini_nanobanana_api") as api:
            self.assertEqual(portraits.generate_icons_for_file(self.path, self.args, ""), (0, True))
            api.assert_not_called()
        self.assertEqual(self.customers()[0]["icon"], icon_path.name)
        self.assertEqual(self.customers()[1]["icon"], "customer.png")

    def test_json_only_does_not_link_empty_portraits(self):
        self.args.json_only = True
        (self.path.parent / "icons/customer-driver-portrait.png").touch()
        before = self.snapshot()
        self.assertEqual(portraits.generate_icons_for_file(self.path, self.args, ""), (0, False))
        self.assertEqual(before, self.snapshot())

    def test_limit_applies_across_domains_without_dangling_references(self):
        other = self.make_domain("beta")
        self.args.limit = 1
        with patch.object(portraits, "PRODUCT_DOMAINS_DIR", self.root), \
             patch.object(portraits, "call_gemini_nanobanana_api", side_effect=self.fake_image) as api:
            self.assertEqual(portraits.run_generation(self.args, "test-key"), 0)
            api.assert_called_once()
        self.assertEqual(self.customers()[1]["icon"], "customer.png")
        self.assertEqual([c["icon"] for c in self.customers(other)], ["customer.png", "customer.png"])

    def test_successful_reference_survives_a_later_api_failure(self):
        with patch.object(portraits, "call_gemini_nanobanana_api", side_effect=[
            self.fake_image(), RuntimeError("Service unavailable"),
        ]):
            with self.assertRaisesRegex(RuntimeError, "Service unavailable"):
                portraits.generate_icons_for_file(self.path, self.args, "test-key")
        self.assertEqual(self.customers()[0]["icon"], "customer-driver-portrait.png")
        self.assertEqual(self.customers()[1]["icon"], "customer.png")
        self.assertFalse((self.path.parent / "icons/customer-rider-portrait.png").exists())

    def test_customer_filter_and_overwrite_handle_a_format_change(self):
        self.args.customer = "driver"
        existing = self.path.parent / "icons/customer-driver-portrait.png"
        existing.write_bytes(PNG_BYTES)
        self.args.overwrite = True
        with patch.object(portraits, "call_gemini_nanobanana_api", return_value=portraits.GeneratedImage(b"jpeg", "jpg")) as api:
            self.assertEqual(portraits.generate_icons_for_file(self.path, self.args, "test-key"), (1, True))
            self.assertEqual(self.customers()[0]["icon"], "customer-driver-portrait.jpg")
            self.assertEqual(self.customers()[1]["icon"], "customer.png")
            self.args.overwrite = False
            self.args.skip_existing = True
            self.assertEqual(portraits.generate_icons_for_file(self.path, self.args, "test-key"), (0, False))
            api.assert_called_once()

    def test_ambiguous_filenames_fail_before_generating(self):
        payload = json.loads(self.path.read_text())
        payload[0]["customers"][0]["id"] = "same-id"
        payload[0]["customers"][1]["id"] = "same_id"
        self.path.write_text(json.dumps(payload))
        with patch.object(portraits, "call_gemini_nanobanana_api") as api:
            with self.assertRaisesRegex(ValueError, "same portrait filename"):
                portraits.generate_icons_for_file(self.path, self.args, "test-key")
            api.assert_not_called()

    def test_extract_image_respects_mime_type_and_ignores_thought_images(self):
        for key, mime_key, mime, suffix in [
            ("inlineData", "mimeType", "image/png", "png"),
            ("inline_data", "mime_type", "image/jpeg", "jpg"),
            ("inlineData", "mimeType", "image/webp", "webp"),
        ]:
            with self.subTest(mime=mime):
                payload = {"candidates": [{"content": {"parts": [
                    {"thought": True, "inlineData": {"mimeType": "image/png", "data": "dGhvdWdodA=="}},
                    {key: {mime_key: mime, "data": base64.b64encode(PNG_BYTES).decode()}},
                ]}}]}
                image = portraits.extract_generated_image(payload)
                self.assertEqual(image.output_format, suffix)
                self.assertEqual(image.image_bytes, PNG_BYTES)
        with self.assertRaisesRegex(RuntimeError, "supported inline image"):
            portraits.extract_generated_image({"candidates": [{"content": {"parts": [{"text": "No image"}]}}]})

    def test_api_uses_square_composition_and_retries_rate_limits(self):
        response_bytes = json.dumps({"candidates": [{"content": {"parts": [{"inlineData": {
            "mimeType": "image/png", "data": base64.b64encode(PNG_BYTES).decode(),
        }}]}}]}).encode()
        target = portraits.build_targets_for_file(self.path, json.loads(self.path.read_text()))[0]
        rate_limit = urllib.error.HTTPError("https://example.invalid", 429, "Rate limit", {}, io.BytesIO(b"retry"))
        with patch.object(portraits.urllib.request, "urlopen", side_effect=[rate_limit, io.BytesIO(response_bytes)]) as urlopen, \
             patch.object(portraits.time, "sleep") as sleep:
            self.assertEqual(portraits.call_gemini_nanobanana_api("test-key", target, self.args).image_bytes, PNG_BYTES)
            self.assertEqual(urlopen.call_count, 2)
            config = json.loads(urlopen.call_args.args[0].data)["generationConfig"]
            self.assertEqual(config["imageConfig"]["aspectRatio"], "1:1")
            sleep.assert_called_once_with(0)
        bad_request = urllib.error.HTTPError("https://example.invalid", 400, "Bad request", {}, io.BytesIO(b"invalid"))
        with patch.object(portraits.urllib.request, "urlopen", side_effect=bad_request) as urlopen:
            with self.assertRaisesRegex(RuntimeError, "Gemini API error 400"):
                portraits.call_gemini_nanobanana_api("test-key", target, self.args)
            urlopen.assert_called_once()

    def test_general_icon_generator_delegates_and_can_skip_customer_work(self):
        with patch.object(domain_icons, "parse_args", return_value=self.args), \
             patch.object(domain_icons, "PRODUCT_DOMAINS_DIR", self.root), \
             patch.dict(os.environ, {"GEMINI_API_KEY": "test-key"}), \
             patch.object(domain_icons, "generate_icon", return_value=False) as other_icons, \
             patch.object(portraits, "call_gemini_nanobanana_api", side_effect=self.fake_image) as api:
            self.assertEqual(domain_icons.main(), 0)
            self.assertEqual(api.call_count, 2)
            self.assertEqual(self.customers()[0]["icon"], "customer-driver-portrait.png")
            self.assertIn("updated 1 JSON files", self.output.getvalue())
            before = self.snapshot()
            self.args.skip_customer_icons = True
            self.args.overwrite = True
            self.assertEqual(domain_icons.main(), 0)
            self.assertEqual(api.call_count, 2)
            self.assertEqual(before, self.snapshot())
            self.assertTrue(all(call.kwargs["path"].name.startswith("kpi-") for call in other_icons.call_args_list))

    def make_wrapper_fixture(self):
        domain_dir = self.root / "data project/_config/product-domains/example-group/alpha"
        domain_dir.mkdir(parents=True)
        stub_dir = self.root / "bin"
        stub_dir.mkdir()
        stub = stub_dir / "python3"
        stub.write_text(
            f"#!{sys.executable}\n"
            "import json, sys\n"
            "from pathlib import Path\n"
            "args = sys.argv[1:]\n"
            "sys.path.insert(0, str(Path(args[0]).resolve().parents[3] / '_wiring'))\n"
            "from domain_paths import resolve_domain_dir\n"
            "domain = resolve_domain_dir(args[args.index('--domain') + 1])\n"
            "print(json.dumps({'args': args, 'domain_dir': str(domain)}))\n"
        )
        stub.chmod(0o755)
        env = {
            **os.environ,
            "PATH": str(stub_dir) + os.pathsep + os.environ.get("PATH", ""),
            "PRODUCTSCAPES_PROJECT": str(self.root / "wrong project"),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        return domain_dir, env

    def test_wrapper_resolves_folder_paths_and_preserves_lightweight_flags(self):
        domain_dir, env = self.make_wrapper_fixture()
        for domain_arg in (str(domain_dir) + "/", os.path.relpath(domain_dir, self.root)):
            for lightweight in (True, False):
                with self.subTest(domain=domain_arg, lightweight=lightweight):
                    flags = ["--lightweight"] if lightweight else []
                    result = subprocess.run(
                        ["bash", str(Path(__file__).resolve().parent / "run.sh"), domain_arg, *flags],
                        cwd=self.root, env=env, check=True, capture_output=True, text=True,
                    )
                    records = [json.loads(line) for line in result.stdout.splitlines()]
                    calls = [record["args"] for record in records]
                    self.assertEqual(len(calls), 5 if lightweight else 6)
                    self.assertTrue(all(record["domain_dir"] == str(domain_dir.resolve()) for record in records))
                    self.assertEqual(Path(calls[0][0]).name, "generate_customer_icons_gemini_nanobanana_api.py")
                    self.assertEqual(
                        [index for index, call in enumerate(calls) if "--lightweight" in call],
                        [1, 2] if lightweight else [],
                    )
                    if lightweight:
                        self.assertFalse(any("generate_missing_domain_icons" in call[0] for call in calls))
                    else:
                        self.assertIn("--skip-customer-icons", calls[-1])

    def test_wrapper_rejects_invalid_folders_and_arguments_before_running_generators(self):
        domain_dir, env = self.make_wrapper_fixture()
        for arguments, message in (
            ([], "Usage:"),
            (["alpha"], "Domain folder does not exist:"),
            ([str(domain_dir / "missing")], "Domain folder does not exist:"),
            ([str(self.path)], "Domain folder does not exist:"),
            ([str(domain_dir.parent)], "Expected a domain folder"),
            ([str(domain_dir), "--unknown"], "Usage:"),
            ([str(domain_dir), "--lightweight", "extra"], "Usage:"),
        ):
            with self.subTest(arguments=arguments):
                result = subprocess.run(
                    ["bash", str(Path(__file__).resolve().parent / "run.sh"), *arguments],
                    cwd=self.root, env=env, capture_output=True, text=True,
                )
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn(message, result.stderr)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
