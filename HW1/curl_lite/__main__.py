"""Allow ``python -m curl_lite`` to behave like the ``curl-lite`` script."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())