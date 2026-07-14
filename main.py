"""Entry point for vikzar-ai scaffold"""

import sys


def main(argv=None):
    argv = argv or sys.argv[1:]
    print("vikzar-ai scaffold created. Use the `app` package to start building your application.")


if __name__ == "__main__":
    main()
