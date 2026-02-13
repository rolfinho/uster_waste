"""Config flow for Uster Waste."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from .const import DOMAIN

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME, default="Uster Waste"): str,
    vol.Required("token", default="").strip(),
    vol.Required("id", default="").strip(),
})


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Uster Waste."""
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        token = user_input["token"].strip()
        waste_id = user_input["id"].strip()
        if not token or not waste_id:
            return self.async_show_form(
                step_id="user", data_schema=DATA_SCHEMA,
                errors={"base": "missing_params"}
            )

        return self.async_create_entry(
            title=user_input[CONF_NAME],
            data={
                CONF_NAME: user_input[CONF_NAME],
                "token": token,
                "id": waste_id,
            }
        )