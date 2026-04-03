#ifndef BSEC_WRAPPER_H
#define BSEC_WRAPPER_H

#include <stdint.h>

#define NUM_USED_OUTPUTS 10
#define NUM_USED_INPUTS  4

typedef struct bsec_result {
    int     n_outputs;
    int     status;
    float   iaq;
    float   static_iaq;
    float   co2_equivalent;
    float   breath_voc_equivalent;
    float   temperature;
	float   humidity;
    float   stab_status;
    float   run_in_status;
    float   gas_percentage;
    float   compensated_gas;
    uint8_t iaq_accuracy;
} bsec_result_t;

typedef struct bsec_settings {
    int      status;
    int64_t  next_call_ns;
    uint16_t heater_temperature;
    uint16_t heater_duration;
    uint8_t  run_gas;
    uint8_t  temperature_oversampling;
    uint8_t  pressure_oversampling;
    uint8_t  humidity_oversampling;
    uint8_t  trigger_measurement;
    uint32_t process_data;
} bsec_settings_t;

int BsecBridge_Init(void);
int BsecBridge_SetConfiguration(void);
int BsecBridge_UpdateSubscription(void);
bsec_settings_t BsecBridge_SensorControl(int64_t timestamp_ns);
bsec_result_t BsecBridge_DoSteps(int64_t timestamp_ns, float temperature, float humidity, float pressure, float gas_resistance, uint32_t process_data);
int BsecBridge_GetState(uint8_t *state_buffer, uint32_t *state_len);
int BsecBridge_SetState(uint8_t *state_buffer, uint32_t state_len);
uint32_t BsecBridge_GetMaxStateSize(void);

#endif /* BSEC_WRAPPER_H */