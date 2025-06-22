import logging, sys

root = logging.getLogger()        # root logger (catches everything)
root.handlers[:] = []             # ① remove handlers that libs installed

h = logging.StreamHandler(sys.stdout)   # ② send everything to stdout
h.setFormatter(logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        "%H:%M:%S"))
root.addHandler(h)

root.setLevel(logging.DEBUG)      # DEBUG, INFO, WARNING …

# ③ (optional) silence noisy third-party libs
for noisy in ("httpcore.http11", "urllib3", "PIL"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
