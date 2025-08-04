import subprocess
import time
import os

NUM_RUNS = 5  # number of full experiments

def run_batch_main():
    print(f"Starting batch of {NUM_RUNS} experiments via `main.py` ...\n")
    start = time.time()

    log_dir = "/Users/etlevn/Documents/PycharmProjects/LLM_Trd/log"
    os.makedirs(log_dir, exist_ok=True)

    for i in range(1, NUM_RUNS + 1):
        print(f"Running Experiment {i}/{NUM_RUNS} ...")
        log_file_path = os.path.join(log_dir, f"exp_{i:03d}.log")
        with open(log_file_path, "w") as log_file:
            process = subprocess.Popen(["python3", "-u", "/Users/etlevn/Documents/PycharmProjects/LLM_Trd/main.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            for line in process.stdout:
                print(line, end="")
                log_file.write(line)
            process.wait()
            result = process

        if result.returncode != 0:
            print(f"Experiment {i} failed with return code {result.returncode}")
            break
        else:
            print(f"Finished Experiment {i}/{NUM_RUNS}\n")
            time.sleep(1)  # prevent directory name collision

    end = time.time()
    print(f"All experiments done in {end - start:.2f} seconds.")

if __name__ == "__main__":
    run_batch_main()