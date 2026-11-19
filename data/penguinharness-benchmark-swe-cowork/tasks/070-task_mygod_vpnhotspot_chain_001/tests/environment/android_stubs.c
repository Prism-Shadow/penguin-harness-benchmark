#include <errno.h>
#include <stddef.h>
#include <stdint.h>
#include <unistd.h>
int __android_log_print(int p, const char *t, const char *f, ...) { (void)p; (void)t; (void)f; return 0; }
int __android_log_write(int p, const char *t, const char *m) { (void)p; (void)t; (void)m; return 0; }
int android_get_device_api_level(void) { return 35; }

int android_setsocknetwork(uint64_t network, int fd) {
    (void)network; (void)fd;
    errno = ENOSYS;
    return -1;
}

int android_res_nsend(uint64_t network, const unsigned char *message, size_t length, uint32_t flags) {
    (void)network; (void)message; (void)length; (void)flags;
    return -ENOSYS;
}

int android_res_nresult(int fd, int *rcode, unsigned char *answer, size_t length) {
    (void)rcode; (void)answer; (void)length;
    if (fd >= 0) close(fd);
    return -ENOSYS;
}

void android_res_cancel(int fd) {
    if (fd >= 0) close(fd);
}
