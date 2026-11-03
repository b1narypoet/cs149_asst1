
import subprocess
import re
import statistics
import matplotlib.pyplot as plt

# 测试的线程数量
thread_counts = [1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 16, 20,24,28,32]

# 每个线程配置重复运行3次
repeats = 3

serial_times = []
parallel_times = []

for n in thread_counts:
    times = []

    for _ in range(repeats):
        result = subprocess.run(
            ["./mandelbrot", "-t", str(n), "-v", "1"],
            capture_output=True,
            text=True
        )

        # 首先检查计算是否正确
        if result.returncode != 0:
            raise RuntimeError(
                f"{n} threads failed:\n"
                + result.stdout[-1500:]
                + result.stderr[-500:]
            )

        serial_match = re.search(
            r"\[mandelbrot serial\]:\s*\[([\d.]+)\]",
            result.stdout
        )
        thread_match = re.search(
            r"\[mandelbrot thread\]:\s*\[([\d.]+)\]",
            result.stdout
        )

        if not serial_match or not thread_match:
            raise RuntimeError("Cannot parse benchmark output")

        serial_times.append(float(serial_match.group(1)))
        times.append(float(thread_match.group(1)))

    parallel_times.append(statistics.median(times))

# 串行参考时间：所有测量值的中位数
serial_time = statistics.median(serial_times)

# 计算加速比
speedups = [serial_time / t for t in parallel_times]

# 输出数据
print("Threads | Time (ms) | Speedup")
for n, t, s in zip(thread_counts, parallel_times, speedups):
    print(f"{n:7d} | {t:9.3f} | {s:6.2f}x")

# 绘制曲线
plt.figure(figsize=(9, 5))

plt.plot(
    thread_counts, speedups,
    marker="o", linewidth=2,
    label="Measured Speedup"
)

plt.plot(
    thread_counts, thread_counts,
    linestyle="--",
    label="Ideal Linear Speedup"
)

plt.xlabel("Number of Threads")
plt.ylabel("Speedup")
plt.title("CS149 Mandelbrot Parallel Speedup")
plt.xticks(thread_counts)
plt.grid(True, alpha=0.3)
plt.legend()
plt.tight_layout()

plt.savefig("speedup.png", dpi=200)
print("Saved speedup.png")
