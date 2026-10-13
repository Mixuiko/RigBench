import unittest
from ghostbench import cpu_workload, summary, cpu_bench, memory_bench

class Tests(unittest.TestCase):
    def test_deterministic_cpu(self):
        self.assertEqual(cpu_workload(10000), cpu_workload(10000))
    def test_median(self):
        self.assertEqual(summary([1, 2, 100])["median"], 2)
    def test_cpu_runs(self):
        result = cpu_bench(2, 10000)
        self.assertTrue(result["checksums_match"])
        self.assertEqual(len(result["samples"]), 2)
    def test_memory_small(self):
        result = memory_bench(2, 1, 4)
        self.assertTrue(result["checksums_match"])
        self.assertEqual(len(result["samples"]), 2)

if __name__ == "__main__":
    unittest.main()
