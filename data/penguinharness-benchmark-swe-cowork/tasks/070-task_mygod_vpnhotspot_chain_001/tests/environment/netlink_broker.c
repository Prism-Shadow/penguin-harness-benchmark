#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <linux/netlink.h>
#include <stdatomic.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <sys/un.h>
#include <unistd.h>

#define FD_LIMIT 65536
static atomic_bool managed[FD_LIMIT];

static int redirected(int descriptor) {
    return descriptor >= 0 && descriptor < FD_LIMIT && managed[descriptor];
}

static int registration(int descriptor, uint32_t groups) {
    unsigned char message[8] = {'V', 'P', 'N', 'B'};
    memcpy(message + 4, &groups, sizeof(groups));
    return send(descriptor, message, sizeof(message), 0) == sizeof(message) ? 0 : -1;
}

int socket(int domain, int type, int protocol) {
    int (*original)(int, int, int) = dlsym(RTLD_NEXT, "socket");
    const char *broker = getenv(protocol == NETLINK_NETFILTER ? "VPNHOTSPOT_NFQUEUE_BROKER" : "VPNHOTSPOT_KERNEL_BROKER");
    if (!broker || domain != AF_NETLINK || (protocol != NETLINK_ROUTE && protocol != NETLINK_NETFILTER))
        return original(domain, type, protocol);
    struct sockaddr_un address = {.sun_family = AF_UNIX};
    size_t length = strlen(broker);
    if (!length || length >= sizeof(address.sun_path) - 1) {
        errno = EINVAL;
        return -1;
    }
    int descriptor = original(AF_UNIX, SOCK_DGRAM | (type & (SOCK_NONBLOCK | SOCK_CLOEXEC)), 0);
    if (descriptor < 0) return -1;
    if (descriptor >= FD_LIMIT) {
        close(descriptor);
        errno = EMFILE;
        return -1;
    }
    int (*original_bind)(int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "bind");
    if (original_bind(descriptor, (struct sockaddr *)&address, sizeof(sa_family_t)) < 0) {
        int saved = errno;
        close(descriptor);
        errno = saved;
        return -1;
    }
    memcpy(address.sun_path + 1, broker, length);
    if (connect(descriptor, (struct sockaddr *)&address, sizeof(sa_family_t) + length + 1) < 0) {
        int saved = errno;
        close(descriptor);
        errno = saved;
        return -1;
    }
    managed[descriptor] = 1;
    return descriptor;
}

int bind(int descriptor, const struct sockaddr *address, socklen_t length) {
    int (*original)(int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "bind");
    if (!redirected(descriptor)) return original(descriptor, address, length);
    if (length < sizeof(struct sockaddr_nl) || address->sa_family != AF_NETLINK) {
        errno = EINVAL;
        return -1;
    }
    return registration(descriptor, ((const struct sockaddr_nl *)address)->nl_groups);
}

int getsockname(int descriptor, struct sockaddr *address, socklen_t *length) {
    int (*original)(int, struct sockaddr *, socklen_t *) = dlsym(RTLD_NEXT, "getsockname");
    if (!redirected(descriptor)) return original(descriptor, address, length);
    struct sockaddr_nl source = {.nl_family = AF_NETLINK, .nl_pid = (uint32_t)descriptor + 1};
    memcpy(address, &source, *length < sizeof(source) ? *length : sizeof(source));
    *length = sizeof(source);
    return 0;
}

int setsockopt(int descriptor, int level, int option, const void *value, socklen_t length) {
    int (*original)(int, int, int, const void *, socklen_t) = dlsym(RTLD_NEXT, "setsockopt");
    if (!redirected(descriptor)) return original(descriptor, level, option, value, length);
    if (level == SOL_NETLINK && option == NETLINK_ADD_MEMBERSHIP) {
        if (length != sizeof(int) || *(const int *)value < 1 || *(const int *)value > 32) {
            errno = EINVAL;
            return -1;
        }
        return registration(descriptor, 1U << (*(const int *)value - 1));
    }
    if (level == SOL_NETLINK && (option == NETLINK_EXT_ACK || option == NETLINK_CAP_ACK || option == NETLINK_NO_ENOBUFS)) return 0;
    return original(descriptor, level, option, value, length);
}

ssize_t sendto(int descriptor, const void *buffer, size_t length, int flags,
               const struct sockaddr *address, socklen_t address_length) {
    ssize_t (*original)(int, const void *, size_t, int, const struct sockaddr *, socklen_t) = dlsym(RTLD_NEXT, "sendto");
    return original(descriptor, buffer, length, flags, redirected(descriptor) ? NULL : address,
                    redirected(descriptor) ? 0 : address_length);
}

ssize_t sendmsg(int descriptor, const struct msghdr *message, int flags) {
    ssize_t (*original)(int, const struct msghdr *, int) = dlsym(RTLD_NEXT, "sendmsg");
    if (!redirected(descriptor)) return original(descriptor, message, flags);
    struct msghdr copy = *message;
    copy.msg_name = NULL;
    copy.msg_namelen = 0;
    return original(descriptor, &copy, flags);
}

ssize_t recvfrom(int descriptor, void *buffer, size_t length, int flags,
                 struct sockaddr *address, socklen_t *address_length) {
    ssize_t (*original)(int, void *, size_t, int, struct sockaddr *, socklen_t *) = dlsym(RTLD_NEXT, "recvfrom");
    if (!redirected(descriptor)) return original(descriptor, buffer, length, flags, address, address_length);
    ssize_t result = original(descriptor, buffer, length, flags, NULL, NULL);
    if (result >= 0 && address && address_length) {
        struct sockaddr_nl source = {.nl_family = AF_NETLINK};
        memcpy(address, &source, *address_length < sizeof(source) ? *address_length : sizeof(source));
        *address_length = sizeof(source);
    }
    return result;
}

ssize_t recvmsg(int descriptor, struct msghdr *message, int flags) {
    ssize_t (*original)(int, struct msghdr *, int) = dlsym(RTLD_NEXT, "recvmsg");
    if (!redirected(descriptor)) return original(descriptor, message, flags);
    struct msghdr copy = *message;
    copy.msg_name = NULL;
    copy.msg_namelen = 0;
    ssize_t result = original(descriptor, &copy, flags);
    message->msg_flags = copy.msg_flags;
    message->msg_controllen = copy.msg_controllen;
    if (result >= 0 && message->msg_name) {
        struct sockaddr_nl source = {.nl_family = AF_NETLINK};
        memcpy(message->msg_name, &source, message->msg_namelen < sizeof(source) ? message->msg_namelen : sizeof(source));
        message->msg_namelen = sizeof(source);
    }
    return result;
}

int close(int descriptor) {
    int (*original)(int) = dlsym(RTLD_NEXT, "close");
    if (descriptor >= 0 && descriptor < FD_LIMIT) managed[descriptor] = 0;
    return original(descriptor);
}
