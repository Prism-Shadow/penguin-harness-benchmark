#!/bin/sh
# Ruby 2.1's launcher supplies legacy libraries to its own process. The browser
# uses the image's native system libraries, including the current libz/libpng.
LD_LIBRARY_PATH= exec /opt/task-browser/libexec/phantomjs "$@"
