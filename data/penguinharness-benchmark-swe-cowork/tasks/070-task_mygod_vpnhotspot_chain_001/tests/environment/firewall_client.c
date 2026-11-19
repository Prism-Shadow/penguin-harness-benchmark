/* Real subprocess boundary for the deterministic firewall fixture.
 * Forward argv/stdin and return the fixture's stdout/exit status. No policies
 * or expectations live here; platform_fixture.restore is the single model. */
#define _POSIX_C_SOURCE 200809L
#include <arpa/inet.h>
#include <errno.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

static void fail(const char *message) { perror(message); exit(125); }
static void transfer(int fd, void *data, size_t length, int writing) {
    unsigned char *cursor = data;
    while (length) {
        ssize_t done = writing ? write(fd, cursor, length) : read(fd, cursor, length);
        if (done < 0 && errno == EINTR) continue;
        if (done <= 0) fail("firewall fixture transfer");
        cursor += done; length -= (size_t)done;
    }
}
static void number(int fd, uint32_t value) {
    value = htonl(value); transfer(fd, &value, sizeof(value), 1);
}
static void string(int fd, const char *value) {
    size_t length = strlen(value);
    if (length > 1048576) exit(125);
    number(fd, (uint32_t)length); transfer(fd, (void *)value, length, 1);
}
int main(int argc, char **argv) {
    const char *name = getenv("VPNHOTSPOT_FIREWALL_BROKER");
    if (!name || strlen(name) + 1 >= sizeof(((struct sockaddr_un *)0)->sun_path)) return 125;
    int fd = socket(AF_UNIX, SOCK_STREAM, 0);
    if (fd < 0) fail("socket");
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    memcpy(address.sun_path + 1, name, strlen(name));
    if (connect(fd, (struct sockaddr *)&address,
                sizeof(address.sun_family) + 1 + strlen(name))) fail("connect");
    number(fd, (uint32_t)argc);
    for (int i = 0; i < argc; ++i) string(fd, argv[i]);
    const char *counters = getenv("VPNHOTSPOT_COUNTER_FIXTURE");
    string(fd, counters ? counters : "");
    unsigned char buffer[65536];
    for (;;) {
        ssize_t count = read(STDIN_FILENO, buffer, sizeof(buffer));
        if (count < 0 && errno == EINTR) continue;
        if (count < 0) fail("stdin");
        number(fd, (uint32_t)count);
        if (!count) break;
        transfer(fd, buffer, (size_t)count, 1);
    }
    uint32_t status, length;
    transfer(fd, &status, sizeof(status), 0);
    transfer(fd, &length, sizeof(length), 0);
    length = ntohl(length);
    while (length) {
        size_t part = length < sizeof(buffer) ? length : sizeof(buffer);
        transfer(fd, buffer, part, 0); transfer(STDOUT_FILENO, buffer, part, 1);
        length -= (uint32_t)part;
    }
    close(fd);
    return (int)ntohl(status);
}
