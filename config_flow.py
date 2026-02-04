"""Config flow for Uster Waste integration."""
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_NAME

from .const import DOMAIN

# Suggested defaults (update these as needed)
DEFAULT_NAME = "Uster Waste Schedule"

DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
    vol.Required("token", default=""): str,
    vol.Required("id", default=""): str,
})


class UsterWasteConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Uster Waste."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, str] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=DATA_SCHEMA)

        token = user_input["token"].strip()
        waste_id = user_input["id"].strip()

        if not token or not waste_id:
            return self.async_show_form(
                step_id="user",
                data_schema=DATA_SCHEMA,
                errors={"base": "missing_params"},
            )

        # Build the URL (store config, not raw URL)
        config = {
            CONF_NAME: user_input[CONF_NAME],
            "token": token,
            "id": waste_id,
        }

        return self.async_create_entry(title=user_input[CONF_NAME], data=config)
