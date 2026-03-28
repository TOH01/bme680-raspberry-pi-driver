#ifndef BSEC_WRAPPER_H
#define BSEC_WRAPPER_H

#include <stdint.h>

#define NUM_USED_OUTPUTS 10

typedef struct {
    int     n_outputs;
    int     status;
    float   iaq;
    float   static_iaq;
    float   co2_equivalent;
    float   breath_voc_equivalent;
    float   temperature;
	float   humidity;
    float   stabStatus;
    float   runInStatus;
    float   gas_percentage;
    float   compensated_gas;
    uint8_t iaq_accuracy;
} bsec_result_t;

int             init_bridge(void);
bsec_result_t bsec_compute(int64_t timestamp_ns, float temperature, float humidity, float pressure, float gas_resistance);
int             bridge_get_state(uint8_t *state_buffer, uint32_t *state_len);
int             bridge_set_state(uint8_t *state_buffer, uint32_t state_len);
uint32_t        bridge_max_state_size(void);

#endif /* BSEC_WRAPPER_H */