#include "vehicle.h"
#include <string.h>

static int sign(int x) { return (x > 0) - (x < 0); }
void Vehicle_Init(Vehicle *v, uint32_t now) {
    memset(v, 0, sizeof(*v)); v->tick = now;
}
void Vehicle_Stop(Vehicle *v) {
    unsigned i;
    for (i = 0; i < 2; ++i) {
        if (v->output[i]) v->zero_since[i] = v->tick;
        v->target[i] = v->output[i] = 0;
    }
    v->valid = 0; v->credit = 0;
}
void Vehicle_Command(Vehicle *v, int left, int right, uint32_t now) {
    unsigned i;
    int pair[2] = {left, right};
    if (left < -100 || left > 100 || right < -100 || right > 100) return;
    if (v->valid && now - v->updated >= VEHICLE_WATCHDOG_MS) {
        v->tick = now; Vehicle_Stop(v);
    }
    v->updated = now; v->valid = 1;
    for (i = 0; i < 2; ++i) {
        v->target[i] = pair[i];
        /* Zero is always immediate; keep direction history across stops. */
        if (!pair[i] && v->output[i]) {
            v->output[i] = 0; v->zero_since[i] = now;
        }
    }
}
void Vehicle_Tick(Vehicle *v, uint32_t now) {
    unsigned i, step;
    uint32_t elapsed = now - v->tick;
    v->tick = now;
    if (!v->valid || now - v->updated >= VEHICLE_WATCHDOG_MS) {
        Vehicle_Stop(v); return;
    }
    /* Never compensate a stalled loop with a large acceleration jump. */
    if (elapsed > 20) elapsed = 20;
    v->credit += elapsed * VEHICLE_RAMP_PER_SECOND;
    step = v->credit / 1000; v->credit %= 1000;
    for (i = 0; i < 2; ++i) {
        int target = v->target[i], out = v->output[i], wanted = sign(target);
        if (!target) continue;
        if (out && sign(out) != wanted) {
            v->output[i] = 0; v->zero_since[i] = now; continue;
        }
        if (!out && v->last_sign[i] && v->last_sign[i] != wanted
                && now - v->zero_since[i] < VEHICLE_REVERSE_MS) continue;
        if (out < target) out += (unsigned)(target - out) < step ? target - out : (int)step;
        else if (out > target) out -= (unsigned)(out - target) < step ? out - target : (int)step;
        v->output[i] = out;
        if (out) v->last_sign[i] = sign(out);
    }
}
static uint8_t crc8(const uint8_t *b, unsigned n) {
    uint8_t c = 0; unsigned i;
    while (n--) { c ^= *b++; for (i = 0; i < 8; ++i) c = (c << 1) ^ ((c & 128) ? 7 : 0); }
    return c;
}
int Packet_Feed(PacketParser *p, Vehicle *v, uint8_t byte, uint32_t now, ServoHandler servo) {
    unsigned length;
    p->bytes[p->count++] = byte;
    while (p->count) {
        uint8_t *b = p->bytes;
        if (b[0] != 0xAA) goto shift;
        if (p->count < 2) return 0;
        if (b[1] == 0x10) length = 8;
        else if (b[1] == 1 || b[1] == 2) length = 6;
        else goto shift;
        if (p->count < length) return 0;
        if (length == 8 && b[2] == 2 && b[3] == 2 && b[7] == 0x55
                && crc8(b + 1, 5) == b[6]) {
            int left = b[4] < 128 ? b[4] : b[4] - 256;
            int right = b[5] < 128 ? b[5] : b[5] - 256;
            if (left >= -100 && left <= 100 && right >= -100 && right <= 100) {
                Vehicle_Command(v, left, right, now); p->count = 0; return 1;
            }
        } else if (length == 6 && b[2] == 1 && b[3] <= 180 && b[5] == 0x55
                && (uint8_t)(b[1] + b[2] + b[3]) == b[4]) {
            if (servo) servo(b[1], b[3]);
            p->count = 0; return 2;
        }
shift:
        --p->count; memmove(p->bytes, p->bytes + 1, p->count);
    }
    return 0;
}
