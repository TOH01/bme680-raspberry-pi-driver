#ifndef BSEC_WRAPPER_H
#define BSEC_WRAPPER_H

#include <stdint.h>

typedef struct {
    float   iaq;
    float   static_iaq;
    uint8_t accuracy;
    int     status;
    int     n_outputs;
} bsec_result_t;

int          init_bridge(void);
bsec_result_t bsec_compute(int64_t timestamp_ns, float temperature, float humidity, float gas_resistance);
int          bridge_get_state(uint8_t *state_buffer, uint32_t *state_len);
int          bridge_set_state(uint8_t *state_buffer, uint32_t state_len);
uint32_t     bridge_max_state_size(void);

#endif /* BSEC_WRAPPER_H */