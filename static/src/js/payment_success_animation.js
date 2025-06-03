/** @odoo-module **/

import { registry } from "@web/core/registry";

registry.category("actions").add("show_payment_success_and_close", (env) => {
    const overlay = document.createElement("div");
    overlay.id = "payment-success-overlay";
    overlay.innerHTML = `
        <div class="success-popup">
            <div class="success-icon">✅</div>
            <div class="success-text">Payment Successful</div>
        </div>
        <style>
            #payment-success-overlay {
                position: fixed;
                top: 0; left: 0;
                width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.75);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                animation: fadeOut 1s ease-out 2s forwards;
            }

            .success-popup {
                text-align: center;
                color: white;
                animation: scaleUp 0.5s ease;
            }

            .success-icon {
                font-size: 70px;
                margin-bottom: 15px;
                text-shadow: 0 0 10px #00ff99;
            }

            .success-text {
                font-size: 36px;
                font-weight: bold;
                text-shadow: 0 0 8px #00ffcc;
            }

            @keyframes fadeOut {
                to { opacity: 0; visibility: hidden; }
            }

            @keyframes scaleUp {
                0% { transform: scale(0.7); opacity: 0; }
                100% { transform: scale(1); opacity: 1; }
            }
        </style>
    `;
    document.body.appendChild(overlay);

    setTimeout(() => {
        overlay.remove();

        // ✅ Properly close wizard using action service
        env.services.action.doAction({ type: "ir.actions.act_window_close" });
    }, 3000);
});

registry.category("actions").add("show_payment_success_animation_only", () => {
    const overlay = document.createElement("div");
    overlay.id = "payment-success-overlay";
    overlay.innerHTML = `
        <div class="success-popup">
            <div class="success-icon">✅</div>
            <div class="success-text">Payment Successful</div>
        </div>
        <style>
            #payment-success-overlay {
                position: fixed;
                top: 0; left: 0;
                width: 100%; height: 100%;
                background: rgba(0, 0, 0, 0.75);
                display: flex;
                align-items: center;
                justify-content: center;
                z-index: 9999;
                animation: fadeOut 1s ease-out 2s forwards;
            }

            .success-popup {
                text-align: center;
                color: white;
                animation: scaleUp 0.5s ease;
            }

            .success-icon {
                font-size: 70px;
                margin-bottom: 15px;
                text-shadow: 0 0 10px #00ff99;
            }

            .success-text {
                font-size: 36px;
                font-weight: bold;
                text-shadow: 0 0 8px #00ffcc;
            }

            @keyframes fadeOut {
                to { opacity: 0; visibility: hidden; }
            }

            @keyframes scaleUp {
                0% { transform: scale(0.7); opacity: 0; }
                100% { transform: scale(1); opacity: 1; }
            }
        </style>
    `;
    document.body.appendChild(overlay);

    // Remove overlay after 3 seconds
    setTimeout(() => {
        overlay.remove();
    }, 3000);
});
