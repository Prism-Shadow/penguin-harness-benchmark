#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <stddef.h>
#include <stdint.h>
#include <unistd.h>

extern int android_get_device_api_level(void);
extern int android_setsocknetwork(uint64_t network, int fd);
extern int android_res_nsend(uint64_t network, const unsigned char *message, size_t length, uint32_t flags);
extern int android_res_nresult(int fd, int *rcode, unsigned char *answer, size_t length);
extern void android_res_cancel(int fd);
extern int __android_log_print(int priority, const char *tag, const char *format, ...);
extern int __android_log_write(int priority, const char *tag, const char *message);

int main(void) {
    int descriptors[2];
    int rcode = 19;
    unsigned char answer[2] = {23, 29};
    assert(android_get_device_api_level() == 35);
    assert(__android_log_print(4, "abi", "%s", "check") == 0);
    assert(__android_log_write(4, "abi", "check") == 0);
    assert(pipe(descriptors) == 0);
    errno = 0;
    assert(android_setsocknetwork(UINT64_C(0x1234567800000063), descriptors[0]) == -1);
    assert(errno == ENOSYS);
    assert(fcntl(descriptors[0], F_GETFD) >= 0);
    assert(android_res_nsend(UINT64_C(0xfedcba9800000063), answer, sizeof(answer), 0) == -ENOSYS);
    assert(android_res_nsend(0, NULL, 0, UINT32_MAX) == -ENOSYS);
    assert(android_res_nresult(descriptors[0], &rcode, answer, sizeof(answer)) == -ENOSYS);
    assert(rcode == 19 && answer[0] == 23 && answer[1] == 29);
    errno = 0;
    assert(fcntl(descriptors[0], F_GETFD) == -1 && errno == EBADF);
    android_res_cancel(descriptors[1]);
    errno = 0;
    assert(fcntl(descriptors[1], F_GETFD) == -1 && errno == EBADF);
    android_res_cancel(-1);
    assert(android_res_nresult(-1, NULL, NULL, 0) == -ENOSYS);
    return 0;
}
