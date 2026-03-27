#include <stdint.h>
#include <string.h>

#include "bsec_interface.h"
#include "bsec_datatypes.h"
#include "bsec_wrapper.h"

int init_bridge(void)
{
    bsec_library_return_t status = bsec_init();

    if (status == BSEC_OK){
        bsec_sensor_configuration_t requested[2];
        requested[0].sensor_id   = BSEC_OUTPUT_IAQ;
        requested[0].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested[1].sensor_id   = BSEC_OUTPUT_STATIC_IAQ;
        requested[1].sample_rate = BSEC_SAMPLE_RATE_LP;

        bsec_sensor_configuration_t required[BSEC_MAX_PHYSICAL_SENSOR];
        uint8_t n_required = BSEC_MAX_PHYSICAL_SENSOR;

        status = bsec_update_subscription(requested, 2, required, &n_required);
    }

    return status;
}

bsec_result_t bsec_compute(int64_t timestamp_ns, float temperature, float humidity, float gas_resistance)
{
    bsec_result_t result;
    memset(&result, 0, sizeof(result));

    bsec_input_t inputs[3];
    inputs[0].sensor_id  = BSEC_INPUT_TEMPERATURE;
    inputs[0].signal     = temperature;
    inputs[0].time_stamp = timestamp_ns;

    inputs[1].sensor_id  = BSEC_INPUT_HUMIDITY;
    inputs[1].signal     = humidity;
    inputs[1].time_stamp = timestamp_ns;

    inputs[2].sensor_id  = BSEC_INPUT_GASRESISTOR;
    inputs[2].signal     = gas_resistance;
    inputs[2].time_stamp = timestamp_ns;

    bsec_output_t outputs[BSEC_NUMBER_OUTPUTS];
    uint8_t       n_outputs = BSEC_NUMBER_OUTPUTS;

    bsec_library_return_t status = bsec_do_steps(inputs, 3, outputs, &n_outputs);
    if (status < BSEC_OK) {
        result.status = (int)status;
        return result;
    }

    result.n_outputs = (int)n_outputs;

    for (uint8_t i = 0; i < n_outputs; i++) {
        if (outputs[i].sensor_id == BSEC_OUTPUT_IAQ) {
            result.iaq      = outputs[i].signal;
            result.accuracy = outputs[i].accuracy;
        } else if (outputs[i].sensor_id == BSEC_OUTPUT_STATIC_IAQ) {
            result.static_iaq = outputs[i].signal;
        }
    }

    return result;
}

int bridge_get_state(uint8_t *state_buffer, uint32_t *state_len)
{
    uint8_t work_buffer[BSEC_MAX_WORKBUFFER_SIZE];
    return bsec_get_state(
        0, state_buffer, BSEC_MAX_STATE_BLOB_SIZE,
        work_buffer, BSEC_MAX_WORKBUFFER_SIZE, state_len
    );
}

int bridge_set_state(uint8_t *state_buffer, uint32_t state_len)
{
    uint8_t work_buffer[BSEC_MAX_WORKBUFFER_SIZE];
    return bsec_set_state(
        state_buffer, state_len,
        work_buffer, BSEC_MAX_WORKBUFFER_SIZE
    );
}

uint32_t bridge_max_state_size(void) 
{ 
    return BSEC_MAX_STATE_BLOB_SIZE; 
}