/**
 * Minimal socket emulation for the Emscripten build of Xash3D-FWGS.
 *
 * The engine expects a POSIX socket layer.  Without one, `socket()` fails and
 * the engine reports "That operation is not supported" when it tries to open
 * the network during a local game.
 *
 * This implementation keeps every socket inside the page and delivers the
 * packets to the socket that is bound to the destination address, so a client
 * and a server running in the same tab can talk to each other.
 */

const LOOPBACK_HOST = 'webxash3d';
const LOOPBACK_ID = 3000;

export function createLoopbackNet() {
    const sockets = new Map();
    let nextHandle = 1000;
    let em = null;
    let errnoLocation = 0;

    // The engine module only exists after it was instantiated, so the net
    // layer is created first and attached later.
    const attach = (module) => {
        em = module;
        errnoLocation = module.Module.ccall('getErrnoLocation', 'number', [], []);
    };

    const addressKey = (ip, port) => `${ip.join('.')}:${port}`;

    function readSockaddr(ptr) {
        const heap = em.HEAPU8;
        return {
            ip: [heap[ptr + 4], heap[ptr + 5], heap[ptr + 6], heap[ptr + 7]],
            port: (heap[ptr + 2] << 8) | heap[ptr + 3],
        };
    }

    function writeSockaddr(ptr, ip, port, socklenPtr) {
        const heap = em.HEAPU8;
        heap[ptr] = 0;
        heap[ptr + 1] = 2; // AF_INET
        heap[ptr + 2] = (port >> 8) & 0xff;
        heap[ptr + 3] = port & 0xff;
        heap[ptr + 4] = ip[0];
        heap[ptr + 5] = ip[1];
        heap[ptr + 6] = ip[2];
        heap[ptr + 7] = ip[3];
        if (socklenPtr) em.HEAP32[socklenPtr >> 2] = 16;
    }

    function deliver(from, data, ip, port) {
        const key = addressKey(ip, port);
        for (const socket of sockets.values()) {
            if (!socket.addr) continue;
            if (addressKey(socket.addr.ip, socket.addr.port) !== key) continue;
            socket.queue.push({ data, ip: from.ip, port: from.port });
            return true;
        }
        return false;
    }

    return {
        attach,

        socket(family, type, protocol) {
            const handle = nextHandle;
            nextHandle += 1;
            sockets.set(handle, { family, type, protocol, addr: null, queue: [] });
            return handle;
        },

        bind(fd, sockaddrPtr, socklenPtr) {
            const socket = sockets.get(fd);
            if (!socket) return -1;
            socket.addr = readSockaddr(sockaddrPtr);
            return 0;
        },

        getsockname(fd, sockaddrPtr, socklenPtr) {
            const socket = sockets.get(fd);
            if (!socket) return -1;
            const addr = socket.addr ?? { ip: [0, 0, 0, 0], port: 0 };
            writeSockaddr(sockaddrPtr, addr.ip, addr.port, socklenPtr);
            return 0;
        },

        connect(fd, sockaddrPtr, socklenPtr) {
            const socket = sockets.get(fd);
            if (!socket) return -1;
            socket.peer = readSockaddr(sockaddrPtr);
            return 0;
        },

        closesocket(fd) {
            return sockets.delete(fd) ? 0 : -1;
        },

        gethostname(namePtr, namelenPtr) {
            em.writeArrayToMemory(
                em.intArrayFromString(`${LOOPBACK_HOST}.${LOOPBACK_ID}`, true),
                namePtr,
            );
            return 0;
        },

        gethostbyname() {
            return 0;
        },

        getaddrinfo(hostnamePtr, restrictPort, hintsPtr, addrinfoPtr) {
            const host = em.AsciiToString(hostnamePtr);
            const identity = Number(host.split('.')[1] ?? LOOPBACK_ID);
            const sockaddr = em._malloc(16);
            writeSockaddr(sockaddr, [101, 101, identity & 0xff, (identity >> 8) & 0xff], 0, 0);

            const info = em._malloc(32);
            em.HEAP32[(info + 4) >> 2] = 2;   // ai_flags
            em.HEAP32[(info + 8) >> 2] = 2;   // ai_family = AF_INET
            em.HEAP32[(info + 12) >> 2] = 2;  // ai_socktype = SOCK_DGRAM
            em.HEAP32[(info + 16) >> 2] = 17; // ai_protocol = IPPROTO_UDP
            em.HEAPU32[(info + 20) >> 2] = sockaddr;
            em.HEAPU32[(info + 24) >> 2] = 0;  // ai_canonname
            em.HEAP32[(info + 28) >> 2] = 0;  // ai_next
            em.HEAPU32[addrinfoPtr >> 2] = info;
            return 0;
        },

        sendto(fd, bufPtr, bufLen, flags, sockaddrPtr, socklenPtr) {
            const socket = sockets.get(fd);
            if (!socket) return -1;
            const target = readSockaddr(sockaddrPtr);
            const source = socket.addr ?? { ip: [101, 101, 0, 0], port: 0 };
            const packet = em.HEAPU8.slice(bufPtr, bufPtr + bufLen);
            deliver(source, packet, target.ip, target.port);
            return bufLen;
        },

        sendto_batch(fd, bufsPtr, lensPtr, flags, sockaddrPtr, socklenPtr) {
            const socket = sockets.get(fd);
            if (!socket) return -1;
            const count = em.HEAP32[lensPtr >> 2];
            const target = readSockaddr(sockaddrPtr);
            const source = socket.addr ?? { ip: [101, 101, 0, 0], port: 0 };
            let total = 0;
            for (let index = 0; index < count; index++) {
                const length = em.HEAP32[(lensPtr >> 2) + index];
                const buffer = em.HEAPU32[(bufsPtr >> 2) + index];
                const packet = em.HEAPU8.slice(buffer, buffer + length);
                deliver(source, packet, target.ip, target.port);
                total += length;
            }
            return total;
        },

        send(fd, bufPtr, bufLen, flags) {
            const socket = sockets.get(fd);
            if (!socket || !socket.peer) return -1;
            const packet = em.HEAPU8.slice(bufPtr, bufPtr + bufLen);
            deliver(socket.addr ?? { ip: [0, 0, 0, 0], port: 0 }, packet, socket.peer.ip, socket.peer.port);
            return bufLen;
        },

        recvfrom(fd, bufPtr, bufLen, flags, sockaddrPtr, socklenPtr) {
            const socket = sockets.get(fd);
            if (!socket) return -1;
            const packet = socket.queue.shift();
            if (!packet) {
                if (errnoLocation) em.setValue(errnoLocation, 73, 'i32'); // EAGAIN
                return -1;
            }
            const length = Math.min(bufLen, packet.data.length);
            em.HEAPU8.set(packet.data.subarray(0, length), bufPtr);
            if (sockaddrPtr) writeSockaddr(sockaddrPtr, packet.ip, packet.port, socklenPtr);
            return length;
        },

        recv(fd, bufPtr, bufLen, flags) {
            const socket = sockets.get(fd);
            if (!socket) return -1;
            const packet = socket.queue.shift();
            if (!packet) return -1;
            const length = Math.min(bufLen, packet.data.length);
            em.HEAPU8.set(packet.data.subarray(0, length), bufPtr);
            return length;
        },

        select() {
            return 0;
        },
    };
}
