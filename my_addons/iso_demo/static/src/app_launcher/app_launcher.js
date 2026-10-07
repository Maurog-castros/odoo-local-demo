/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";
import { Component } from "@odoo/owl";

export class IsoDemoAppLauncher extends Component {
    static template = "iso_demo.AppLauncher";
    static props = { ...standardActionServiceProps };

    setup() {
        this.menuService = useService("menu");
    }

    get apps() {
        return this.menuService
            .getApps()
            .filter((app) => app.xmlid !== "iso_demo.menu_app_launcher");
    }

    iconSource(app) {
        const icon = app.webIconData;
        if (!icon) {
            return "/web/static/img/default_icon_app.png";
        }
        if (icon.startsWith("data:image")) {
            return icon;
        }
        const mimeType = icon.startsWith("P") ? "image/svg+xml" : "image/png";
        return `data:${mimeType};base64,${icon.replace(/\s/g, "")}`;
    }

    openApp(app) {
        return this.menuService.selectMenu(app);
    }
}

registry.category("actions").add("iso_demo.app_launcher", IsoDemoAppLauncher);
