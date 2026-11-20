#define _GNU_SOURCE
#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <netinet/in.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <sys/uio.h>
#include <sys/un.h>
#include <sys/utsname.h>
#include <unistd.h>

#define TRANSPORT_LIMIT 65536
static atomic_int raw_socket[TRANSPORT_LIMIT];
static atomic_int outbound[TRANSPORT_LIMIT];
static atomic_int failure[TRANSPORT_LIMIT];
static uint64_t networks[TRANSPORT_LIMIT];
static struct sockaddr_in6 sources[TRANSPORT_LIMIT];
static struct sockaddr_in6 destinations[TRANSPORT_LIMIT];

static int valid(int descriptor) {
    return descriptor >= 0 && descriptor < TRANSPORT_LIMIT;
}

static void observation(const char *event, int descriptor, uint64_t network, int error) {
    const char *root = getenv("VPNHOTSPOT_TRANSPORT_FIXTURE");
    if (!root) return;
    char path[PATH_MAX], line[256];
    snprintf(path, sizeof(path), "%s/transport.jsonl", root);
    int file = open(path, O_WRONLY | O_CREAT | O_APPEND | O_CLOEXEC | O_NOFOLLOW, 0644);
    if (file < 0 || fchmod(file, 0644) < 0) abort();
    int size = snprintf(line, sizeof(line), "{\"event\":\"%s\",\"fd\":%d,\"network\":%llu,\"errno\":%d}\n",
                        event, descriptor, (unsigned long long)network, error);
    ssize_t (*original_write)(int, const void *, size_t) = dlsym(RTLD_NEXT, "write");
    if (original_write(file, line, (size_t)size) != size) abort();
    close(file);
}

static int settings(struct sockaddr_in6 *destination, unsigned int *port, int *error) {
    const char *root = getenv("VPNHOTSPOT_TRANSPORT_FIXTURE");
    if (!root) return 0;
    char path[PATH_MAX], address[INET6_ADDRSTRLEN];
    unsigned int destination_port;
    snprintf(path, sizeof(path), "%s/transport.txt", root);
    FILE *file = fopen(path, "r");
    if (!file) return 0;
    int count = fscanf(file, "%45s %u %u %d", address, &destination_port, port, error);
    fclose(file);
    if (count != 4 || destination_port > 65535 || *port > 65535) abort();
    memset(destination, 0, sizeof(*destination));
    destination->sin6_family = AF_INET6;
    destination->sin6_port = htons((uint16_t)destination_port);
    if (inet_pton(AF_INET6, address, &destination->sin6_addr) != 1) abort();
    return 1;
}

int uname(struct utsname *value) {
    int (*original)(struct utsname *) = dlsym(RTLD_NEXT, "uname");
    int result = original(value);
    const char *release = getenv("VPNHOTSPOT_KERNEL_RELEASE");
    if (!result && release) snprintf(value->release, sizeof(value->release), "%s", release);
    return result;
}

int android_setsocknetwork(uint64_t network, int descriptor) {
    int (*original)(uint64_t, int) = dlsym(RTLD_NEXT, "android_setsocknetwork");
    if (!getenv("VPNHOTSPOT_TRANSPORT_FIXTURE")) return original(network, descriptor);
    if (!valid(descriptor)) { errno = EBADF; return -1; }
    networks[descriptor] = network;
    outbound[descriptor] = 1;
    observation("network", descriptor, network, 0);
    return 0;
}

int socket(int domain, int type, int protocol) {
    int (*original)(int, int, int) = dlsym(RTLD_NEXT, "socket");
    const char *broker = getenv("VPNHOTSPOT_RAW_BROKER");
    if (!broker || domain != AF_INET6 || (type & 15) != SOCK_RAW || protocol != IPPROTO_ICMPV6)
        return original(domain, type, protocol);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    size_t length = strlen(broker);
    if (!length || length >= sizeof(address.sun_path) - 1) { errno = EINVAL; return -1; }
    int descriptor = original(AF_UNIX, SOCK_DGRAM | (type & (SOCK_NONBLOCK | SOCK_CLOEXEC)), 0);
    if (descriptor < 0) return descriptor;
    if (!valid(descriptor)) { close(descriptor); errno = EMFILE; return -1; }
    if (bind(descriptor, (struct sockaddr *)&address, sizeof(sa_family_t)) < 0) {
        int saved = errno; close(descriptor); errno = saved; return -1;
    }
    memcpy(address.sun_path + 1, broker, length);
    if (connect(descriptor, (struct sockaddr *)&address, sizeof(sa_family_t) + length + 1) < 0) {
        int saved = errno; close(descriptor); errno = saved; return -1;
    }
    raw_socket[descriptor] = 1;
    return descriptor;
}

int bind(int descriptor, const struct sockaddr *address, socklen_t length) {
    int (*original)(int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "bind");
    if (!valid(descriptor) || !raw_socket[descriptor]) return original(descriptor, address, length);
    if (length < sizeof(struct sockaddr_in6) || address->sa_family != AF_INET6) { errno = EINVAL; return -1; }
    sources[descriptor] = *(const struct sockaddr_in6 *)address;
    return 0;
}

int setsockopt(int descriptor, int level, int option, const void *value, socklen_t length) {
    int (*original)(int, int, int, const void *, socklen_t) = dlsym(RTLD_NEXT, "setsockopt");
    if (valid(descriptor) && raw_socket[descriptor] && level == IPPROTO_IPV6 && option == IPV6_TRANSPARENT &&
        getenv("VPNHOTSPOT_ICMP_UNAVAILABLE")) {
        observation("icmp-capability", descriptor, 0, EOPNOTSUPP);
        errno = EOPNOTSUPP;
        return -1;
    }
    if (valid(descriptor) && raw_socket[descriptor] &&
        ((level == SOL_SOCKET && (option == SO_MARK || option == SO_BINDTODEVICE)) ||
         (level == IPPROTO_IPV6 && (option == IPV6_TRANSPARENT || option == IPV6_RECVERR || option == IPV6_UNICAST_HOPS || option == IPV6_MULTICAST_HOPS))))
        return 0;
    return original(descriptor, level, option, value, length);
}

static void accepted(int descriptor) {
    unsigned int port;
    int error;
    struct sockaddr_in6 actual;
    socklen_t length = sizeof(actual);
    int (*original)(int, struct sockaddr *, socklen_t *) = dlsym(RTLD_NEXT, "getsockname");
    if (valid(descriptor) && !original(descriptor, (struct sockaddr *)&actual, &length) && actual.sin6_family == AF_INET6)
        settings(&destinations[descriptor], &port, &error);
}

int accept(int descriptor, struct sockaddr *address, socklen_t *length) {
    int (*original)(int, struct sockaddr *, socklen_t *) = dlsym(RTLD_NEXT, "accept");
    int result = original(descriptor, address, length);
    accepted(result);
    return result;
}

int accept4(int descriptor, struct sockaddr *address, socklen_t *length, int flags) {
    int (*original)(int, struct sockaddr *, socklen_t *, int) = dlsym(RTLD_NEXT, "accept4");
    int result = original(descriptor, address, length, flags);
    accepted(result);
    return result;
}

int getsockname(int descriptor, struct sockaddr *address, socklen_t *length) {
    int (*original)(int, struct sockaddr *, socklen_t *) = dlsym(RTLD_NEXT, "getsockname");
    if (!valid(descriptor) || !destinations[descriptor].sin6_family) return original(descriptor, address, length);
    memcpy(address, &destinations[descriptor], *length < sizeof(struct sockaddr_in6) ? *length : sizeof(struct sockaddr_in6));
    *length = sizeof(struct sockaddr_in6);
    return 0;
}

int connect(int descriptor, const struct sockaddr *address, socklen_t length) {
    int (*original)(int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "connect");
    if (!valid(descriptor) || !outbound[descriptor] || raw_socket[descriptor] || address->sa_family != AF_INET6)
        return original(descriptor, address, length);
    struct sockaddr_in6 destination;
    unsigned int port;
    int error;
    if (!settings(&destination, &port, &error)) return original(descriptor, address, length);
    observation("connect", descriptor, networks[descriptor], 0);
    failure[descriptor] = error;
    destination.sin6_addr = in6addr_loopback;
    destination.sin6_port = htons((uint16_t)port);
    return original(descriptor, (struct sockaddr *)&destination, sizeof(destination));
}

static int fail_write(int descriptor) {
    if (!valid(descriptor) || !outbound[descriptor]) return 0;
    int error = atomic_exchange(&failure[descriptor], 0);
    if (error) { observation("injected", descriptor, networks[descriptor], error); errno = error; }
    return error;
}

ssize_t write(int descriptor, const void *buffer, size_t length) {
    ssize_t (*original)(int, const void *, size_t) = dlsym(RTLD_NEXT, "write");
    return fail_write(descriptor) ? -1 : original(descriptor, buffer, length);
}

ssize_t writev(int descriptor, const struct iovec *vectors, int count) {
    ssize_t (*original)(int, const struct iovec *, int) = dlsym(RTLD_NEXT, "writev");
    return fail_write(descriptor) ? -1 : original(descriptor, vectors, count);
}

ssize_t send(int descriptor, const void *buffer, size_t length, int flags) {
    ssize_t (*original)(int, const void *, size_t, int) = dlsym(RTLD_NEXT, "send");
    return fail_write(descriptor) ? -1 : original(descriptor, buffer, length, flags);
}

ssize_t sendto(int descriptor, const void *buffer, size_t length, int flags,
               const struct sockaddr *address, socklen_t address_length) {
    ssize_t (*original)(int, const void *, size_t, int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "sendto");
    if (fail_write(descriptor)) return -1;
    if (!valid(descriptor) || !raw_socket[descriptor]) return original(descriptor, buffer, length, flags, address, address_length);
    if (!address || address_length < sizeof(struct sockaddr_in6) || length > 65536) { errno = EINVAL; return -1; }
    unsigned char packet[65536 + 64];
    memcpy(packet, &networks[descriptor], 8);
    memcpy(packet + 8, &sources[descriptor], 28);
    memcpy(packet + 36, address, 28);
    memcpy(packet + 64, buffer, length);
    ssize_t result = original(descriptor, packet, length + 64, flags, NULL, 0);
    return result < 0 ? result : result - 64;
}

ssize_t recvmsg(int descriptor, struct msghdr *message, int flags) {
    ssize_t (*original)(int, struct msghdr *, int) = dlsym(RTLD_NEXT, "recvmsg");
    if (!valid(descriptor) || !raw_socket[descriptor]) return original(descriptor, message, flags);
    if (flags & MSG_ERRQUEUE) { errno = EAGAIN; return -1; }
    unsigned char packet[65536 + 28];
    struct iovec vector = {.iov_base = packet, .iov_len = sizeof(packet)};
    struct msghdr input = {.msg_iov = &vector, .msg_iovlen = 1};
    ssize_t result = original(descriptor, &input, flags);
    if (result < 0) return result;
    if (result < 28) { errno = EPROTO; return -1; }
    if (message->msg_name) memcpy(message->msg_name, packet, message->msg_namelen < 28 ? message->msg_namelen : 28);
    message->msg_namelen = 28;
    message->msg_controllen = 0;
    size_t copied = 0, size = (size_t)result - 28;
    for (size_t index = 0; index < message->msg_iovlen && copied < size; index++) {
        size_t count = message->msg_iov[index].iov_len;
        if (count > size - copied) count = size - copied;
        memcpy(message->msg_iov[index].iov_base, packet + 28 + copied, count);
        copied += count;
    }
    message->msg_flags = copied < size ? MSG_TRUNC : 0;
    return (ssize_t)copied;
}

ssize_t recvfrom(int descriptor, void *buffer, size_t length, int flags,
                 struct sockaddr *address, socklen_t *address_length) {
    ssize_t (*original)(int, void *, size_t, int, struct sockaddr *, socklen_t *) = dlsym(RTLD_NEXT, "recvfrom");
    if (!valid(descriptor) || !raw_socket[descriptor]) return original(descriptor, buffer, length, flags, address, address_length);
    struct iovec vector = {.iov_base = buffer, .iov_len = length};
    struct msghdr message = {.msg_name = address, .msg_namelen = address_length ? *address_length : 0,
                            .msg_iov = &vector, .msg_iovlen = 1};
    ssize_t result = recvmsg(descriptor, &message, flags);
    if (result >= 0 && address_length) *address_length = message.msg_namelen;
    return result;
}

ssize_t sendmsg(int descriptor, const struct msghdr *message, int flags) {
    ssize_t (*original)(int, const struct msghdr *, int) = dlsym(RTLD_NEXT, "sendmsg");
    if (!valid(descriptor) || !raw_socket[descriptor])
        return fail_write(descriptor) ? -1 : original(descriptor, message, flags);
    unsigned char packet[65536];
    size_t size = 0;
    for (size_t index = 0; index < message->msg_iovlen; index++) {
        if (message->msg_iov[index].iov_len > sizeof(packet) - size) { errno = EMSGSIZE; return -1; }
        memcpy(packet + size, message->msg_iov[index].iov_base, message->msg_iov[index].iov_len);
        size += message->msg_iov[index].iov_len;
    }
    return sendto(descriptor, packet, size, flags, message->msg_name, message->msg_namelen);
}

int close(int descriptor) {
    int (*original)(int) = dlsym(RTLD_NEXT, "close");
    if (valid(descriptor)) {
        raw_socket[descriptor] = outbound[descriptor] = failure[descriptor] = 0;
        networks[descriptor] = 0;
        memset(&sources[descriptor], 0, sizeof(sources[descriptor]));
        memset(&destinations[descriptor], 0, sizeof(destinations[descriptor]));
    }
    return original(descriptor);
}
