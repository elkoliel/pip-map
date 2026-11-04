import tempfile
import unittest
from pathlib import Path

from pip_map import format_size, scan_distributions


class FakeDistribution:
    def __init__(self, root, name, version, files):
        self.root = Path(root)
        self.metadata = {"Name": name, "Version": version}
        self.version = version
        self.files = files

    def locate_file(self, path):
        if str(path) == "":
            return self.root
        return self.root / str(path)


class PipMapTests(unittest.TestCase):
    def test_format_size_uses_binary_units(self):
        self.assertEqual(format_size(0), "0 B")
        self.assertEqual(format_size(1024), "1.00 KiB")
        self.assertEqual(format_size(1024 * 1024), "1.00 MiB")

    def test_environment_total_deduplicates_shared_files(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "shared.bin").write_bytes(b"s" * 1024)
            (root / "alpha.bin").write_bytes(b"a" * 256)
            (root / "beta.bin").write_bytes(b"b" * 512)

            alpha = FakeDistribution(
                root, "alpha", "1.0", ["shared.bin", "alpha.bin"]
            )
            beta = FakeDistribution(
                root, "beta", "2.0", ["shared.bin", "beta.bin"]
            )

            result = scan_distributions([alpha, beta])

            self.assertEqual(result.summary.total_distributions, 2)
            self.assertEqual(result.summary.unique_files_measured, 3)
            self.assertEqual(result.summary.estimated_unique_size_bytes, 1792)
            self.assertEqual(result.packages[0].size_bytes, 1280)
            self.assertEqual(result.packages[1].size_bytes, 1536)

    def test_missing_file_inventory_is_reported_as_unknown(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            distribution = FakeDistribution(
                temporary_directory, "no-record", "1.0", None
            )
            result = scan_distributions([distribution])

            self.assertIsNone(result.packages[0].size_bytes)
            self.assertEqual(
                result.summary.distributions_without_file_inventory, 1
            )


if __name__ == "__main__":
    unittest.main()
