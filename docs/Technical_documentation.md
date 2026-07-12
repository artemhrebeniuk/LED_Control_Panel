# Technical Documentation: Architecture and Scalable Configuration of the LED Screen

## 1. Hardware Components and Expansion Potential (Hardware)
The system is a modular LED display designed with high scalability and remote software control capabilities over a wired local area network (LAN).

* **Media Player (Controller):** `Beijing Kystar KD6` — an Android-based control microcomputer responsible for storing media files, processing network commands, and encoding the video stream. It features **6 independent gigabit LED OUT ports**, allowing for significant future screen expansions without needing to replace the controller.
* **Receiving Card (Port Board):** `Kystar G616` — a HUB75 interface expansion board that distributes pixel data to specific LED matrices. The card is equipped with **16 ports (JH1–JH16)**, providing a massive buffer for connecting additional daisy-chained panels.
* **LED Modules (Panels):** Magnetic LED display panels (P4 format).
* **Power Supply Unit (PSU):** A switching metal power supply unit (Input: 220V AC, Output: 5V DC). It delivers high-amperage power to both the LED matrices and the G616 receiving card.

---

## 2. Current Screen Geometry and Modular Principle (Geometry)
The initial screen configuration is assembled as a **2x2** cluster (two panels horizontally, two panels vertically). The entire structure is fully modular, meaning the architecture is engineered to seamlessly accommodate new modules in any direction in the future.

* **Physical Resolution of a Single LED Module:** 80 pixels (width) × 40 pixels (height).
* **Current Cluster Configuration (Initial Phase):**
    * **Current Width ($W$):** $80 \text{ pixels} \times 2 \text{ panels} = 160$ pixels.
    * **Current Height ($H$):** $40 \text{ pixels} \times 2 \text{ panels} = 80$ pixels.
* **Total Pixel Area at Launch:** 12,800 individual LEDs.

---

## 3. Wiring and Connection Diagram (Wiring)

### A. Power Lines
1. **Media Player KD6:** Powered independently via its own 220V power adapter (the barrel plug connects to the `DC 5V/12V` jack on the rear panel).
2. **G616 Receiving Card:** Connects to the silver PSU via a 2-pin screw terminal located in the upper-left corner of the board. Polarity: Red wire $\rightarrow$ `+5V`, Black wire $\rightarrow$ `GND`.
3. **LED Panels:** Each module connects to the power lines of the silver PSU using white plastic 4-pin power connectors.

### B. Data Lines
1. **Computer $\rightarrow$ Media Player (Control Line):** A network LAN cable runs directly from the Windows laptop's network card to the **dedicated control service port** of the KD6 media player (located on the far right of the rear panel, between the USB 3.0 port and the DC power jack).
2. **Media Player $\rightarrow$ Receiving Card (Data Stream):** A network LAN cable runs from the dedicated **LED OUT 1** port (located on the left side of the player's rear panel) to the metal RJ45 network port of the G616 receiving card.
3. **Receiving Card $\rightarrow$ LED Screen:** A grey flat 16-pin HUB75 ribbon cable runs from the **JH1** port on the G616 board into the input connector (**IN**) of the first LED panel.
4. **Panel $\rightarrow$ Panel (Daisy Chain):** The signal is transmitted sequentially from one module to the next via grey ribbon cables (running from the **OUT** connector of the previous panel to the **IN** connector of the next, following the arrows indicated on the panel boards).

---

## 4. Network Infrastructure (LAN Settings)
When connected directly via a LAN cable, the computer and the media player form an isolated wired local area network.

* **Network IP Address of the Player via LAN Interface:** `169.254.250.250`.
* **Connection Status in Windows:** Will display as *"Unidentified network (No internet access)"*, which is the expected behavior when linked directly to the controller.

---

## 5. Software Interface Specification (LAN API)
The media player acts as a local web server, processing incoming HTTP requests from the computer via the LAN cable on ports **18080** and **18081**.

* **Base URL for API Requests:** `http://169.254.250.250:18080/`

### Key API Endpoints:
* **Instant Text Rendering:** `POST /playText` (Parameters: `text`, `width`, `height`, `scrollSpeed`, `color`, `textSize`).
* **Web Page/Interface Rendering:** `POST /playWeb` (Parameters: `url`, `width`, `height`).
* **Software Brightness Control:** `POST /setting/bright` (Parameters: `bright` from 0 to 100).
* **Dynamic Window Configuration:** `POST /setWindows` (Sends a JSON array with layer coordinates: `x`, `y`, `w`, `h`).

---

## 6. Dynamic Scaling Logic Template for AI-Assisted Development (Scaling Code Template)
To prevent having to rewrite the source code when scaling up the number of panels, the AI assistant must exclusively use dynamic grid calculation. Hardcoding the final screen resolution is prohibited.

```python
# ====================================================================
# LED SCREEN DYNAMIC SCALING PARAMETERS & CONSTANTS
# ====================================================================

# Physical matrix dimensions of a single base panel (static)
PANEL_WIDTH = 80
PANEL_HEIGHT = 40

# Current grid configuration (modify only these values when expanding the screen)
SCREEN_COLS = 2  # Number of columns (horizontal panels along X-axis)
SCREEN_ROWS = 2  # Number of rows (vertical panels along Y-axis)

# Automatic dynamic calculation of the total resolution for the API
TOTAL_WIDTH = PANEL_WIDTH * SCREEN_COLS    # Calculated canvas width
TOTAL_HEIGHT = PANEL_HEIGHT * SCREEN_ROWS  # Calculated canvas height

# Example function to generate standard payload parameters for the API (e.g., playText / playWeb)
def get_screen_payload(extra_params=None):
    payload = {
        "width": TOTAL_WIDTH,
        "height": TOTAL_HEIGHT
    }
    if extra_params:
        payload.update(extra_params)
    return payload