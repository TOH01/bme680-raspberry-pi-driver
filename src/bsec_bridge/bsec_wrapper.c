#include <stdint.h>
#include <string.h>

#include "bsec_interface.h"
#include "bsec_datatypes.h"
#include "bsec_wrapper.h"
#include "bsec_iaq.h"

int init_bridge(void)
{
    bsec_sensor_configuration_t     requested_virtual_sensors[NUM_USED_OUTPUTS];
    uint8_t                         n_requested_virtual_sensors                          = NUM_USED_OUTPUTS;
    bsec_sensor_configuration_t     required_sensor_settings[BSEC_MAX_PHYSICAL_SENSOR];
    uint8_t                         n_required_sensor_settings                           = BSEC_MAX_PHYSICAL_SENSOR;
    bsec_library_return_t           status                                               = BSEC_OK;
    
    status = bsec_init();
    
    uint8_t work_buffer[BSEC_MAX_WORKBUFFER_SIZE];
    status = bsec_set_configuration(bsec_config_iaq, sizeof(bsec_config_iaq), work_buffer, BSEC_MAX_WORKBUFFER_SIZE);

    if (status == BSEC_OK){
        requested_virtual_sensors[0].sensor_id = BSEC_OUTPUT_IAQ;
        requested_virtual_sensors[0].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[1].sensor_id = BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE;
        requested_virtual_sensors[1].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[2].sensor_id = BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY;
        requested_virtual_sensors[2].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[3].sensor_id = BSEC_OUTPUT_STATIC_IAQ;
        requested_virtual_sensors[3].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[4].sensor_id = BSEC_OUTPUT_CO2_EQUIVALENT;
        requested_virtual_sensors[4].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[5].sensor_id = BSEC_OUTPUT_BREATH_VOC_EQUIVALENT;
        requested_virtual_sensors[5].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[6].sensor_id = BSEC_OUTPUT_STABILIZATION_STATUS;
        requested_virtual_sensors[6].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[7].sensor_id = BSEC_OUTPUT_RUN_IN_STATUS;
        requested_virtual_sensors[7].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[8].sensor_id = BSEC_OUTPUT_GAS_PERCENTAGE;
        requested_virtual_sensors[8].sample_rate = BSEC_SAMPLE_RATE_LP;
        requested_virtual_sensors[9].sensor_id = BSEC_OUTPUT_COMPENSATED_GAS;
        requested_virtual_sensors[9].sample_rate = BSEC_SAMPLE_RATE_LP;

        status = bsec_update_subscription(requested_virtual_sensors, n_requested_virtual_sensors, 
            required_sensor_settings, &n_required_sensor_settings);
    }
    return status;
}

bsec_settings_t bridge_sensor_control(int64_t timestamp_ns)
{
    bsec_settings_t result;
    memset(&result, 0, sizeof(result));
 
    bsec_bme_settings_t settings;
    bsec_sensor_control(timestamp_ns, &settings);
 
    result.next_call_ns             = settings.next_call;
    result.heater_temperature       = settings.heater_temperature;
    result.heater_duration          = settings.heater_duration;
    result.run_gas                  = settings.run_gas;
    result.temperature_oversampling = settings.temperature_oversampling;
    result.pressure_oversampling    = settings.pressure_oversampling;
    result.humidity_oversampling    = settings.humidity_oversampling;
    result.trigger_measurement      = settings.trigger_measurement;
    result.process_data             = settings.process_data;
 
    return result;
}

bsec_result_t bsec_compute(int64_t timestamp_ns, float temperature, float humidity, float pressure, float gas_resistance)
{
    bsec_result_t           bsec_result                         = {0};
    bsec_input_t            inputs[4];
    bsec_library_return_t   status;
    bsec_output_t           bsec_outputs[BSEC_NUMBER_OUTPUTS];
    uint8_t                 num_bsec_outputs                    = BSEC_NUMBER_OUTPUTS;

    inputs[0].sensor_id  = BSEC_INPUT_TEMPERATURE;
    inputs[0].signal     = temperature;
    inputs[0].time_stamp = timestamp_ns;

    inputs[1].sensor_id  = BSEC_INPUT_HUMIDITY;
    inputs[1].signal     = humidity;
    inputs[1].time_stamp = timestamp_ns;

    inputs[2].sensor_id  = BSEC_INPUT_PRESSURE;
    inputs[2].signal     = pressure;
    inputs[2].time_stamp = timestamp_ns;

    inputs[3].sensor_id  = BSEC_INPUT_GASRESISTOR;
    inputs[3].signal     = gas_resistance;
    inputs[3].time_stamp = timestamp_ns;

    status = bsec_do_steps(inputs, 4, bsec_outputs, &num_bsec_outputs);
    
    if (status < BSEC_OK) {
        bsec_result.status = (int)status;
        return bsec_result;
    }

    bsec_result.n_outputs = (int)num_bsec_outputs;

    for (uint8_t index = 0; index < num_bsec_outputs; index++) {
        switch (bsec_outputs[index].sensor_id)
        {
			case BSEC_OUTPUT_IAQ:
                bsec_result.iaq = bsec_outputs[index].signal;
                bsec_result.iaq_accuracy = bsec_outputs[index].accuracy;
                break;
            case BSEC_OUTPUT_STATIC_IAQ:
                bsec_result.static_iaq = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_CO2_EQUIVALENT:
                bsec_result.co2_equivalent = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_BREATH_VOC_EQUIVALENT:
                bsec_result.breath_voc_equivalent = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_TEMPERATURE:
                bsec_result.temperature = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_SENSOR_HEAT_COMPENSATED_HUMIDITY:
                bsec_result.humidity = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_STABILIZATION_STATUS:
                bsec_result.stabStatus = bsec_outputs[index].signal;
                break;
			case BSEC_OUTPUT_RUN_IN_STATUS:
                bsec_result.runInStatus = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_GAS_PERCENTAGE:
                bsec_result.gas_percentage = bsec_outputs[index].signal;
                break;
            case BSEC_OUTPUT_COMPENSATED_GAS:
                bsec_result.compensated_gas = bsec_outputs[index].signal;
                break;
            default:
                continue;
        }
    }
    return bsec_result;
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