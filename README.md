# Beijing Kystar KD6 LED Control Interface

[![PyQt6](https://img.shields.io/badge/UI-PyQt6-blue.svg?style=flat-square&logo=qt)](https://www.qt.io/)
[![FFmpeg](https://img.shields.io/badge/Video_Engine-FFmpeg-green.svg?style=flat-square&logo=ffmpeg)](https://ffmpeg.org/)
[![Python](https://img.shields.io/badge/Language-Python_3.13-yellow.svg?style=flat-square&logo=python)](https://www.python.org/)
[![Network](https://img.shields.io/badge/Protocol-HTTP_LAN-orange.svg?style=flat-square)](#)

A high-performance, multithreaded LAN control system for managing modular LED display panels driven by the **Beijing Kystar KD6** media player.

---

## 📐 System Topology Diagram

```text
+------------------+         HTTP API (Port 18080)         +--------------------+
|  Control PC      | ====================================> | Beijing Kystar KD6 |
|  (PyQt6 App)     |                                       | (Media Player)     |
+------------------+                                       +--------------------+
                                                                     ||
                                                                     || LED OUT 1
                                                                     \/
+------------------+          HUB75 Ribbon Cable           +--------------------+
|   LED Matrix     | <==================================== |    Kystar G616     |
|   (2x2 Panels)   |                                       |  (Receiving Card)  |
+------------------+                                       +--------------------+
```

---

## ⚙️ Technical Specifications

| Parameter | Configuration Specification | Implementation Detail |
| :--- | :--- | :--- |
| **Media Controller** | Beijing Kystar KD6 | Android Controller, 6x LED OUT Ports |
| **Receiving Card** | Kystar G616 | HUB75 Interface Board, 16x Ports |
| **Grid Dimensions** | 2 × 2 Panels (Fully Scalable) | Adjustable via `src/core/config.py` |
| **Panel Resolution** | 80 × 40 Pixels | Standard P4 Module |
| **Total Canvas Size** | 160 × 80 Pixels | Dynamic canvas bounds |
| **Target Frame Rate** | 30 FPS | Hardware ceiling constraint |
| **Control Link** | HTTP via LAN (APIPA) | IP: `169.254.250.250` (Port 18080) |

---

## 📁 Directory Structure & Architectural Layout

```text
.
├── data/                          # Persistent Configurations
│   ├── hardware_config.json       # Physical grid dimensions
│   └── playlists.json             # Stored playlist databases
├── docs/                          # Original SDK Reference Material
│   ├── LAN_secondary_development.md
│   └── Technical_documentation.md
├── src/                           # Codebase Root
│   ├── core/                      # Business & Control Subsystems
│   │   ├── config.py              # Configuration Singleton
│   │   ├── ffmpeg_renderer.py     # Multi-window Canvas Renderer
│   │   ├── kystar_client.py       # API Client Wrapper
│   │   ├── media_utils.py         # File Probe & Validation
│   │   └── playlists_manager.py   # Playlist Persistence Layer
│   └── ui/                        # PyQt6 Interface Layer
│       ├── main_window.py         # Primary GUI
│       ├── scene_editor.py        # Grid / Window Editor
│       ├── styles.py              # UI/UX Stylesheets
│       └── workers.py             # Asynchronous Threads
└── main.py                        # Execution Entry Point
```

---

## 🖥 Core Architectural Modules

### 1. Asynchronous Multithreading
To ensure the GUI thread remains responsive during intensive network operations and file rendering, all core operations are delegated to dedicated `QThread` workers:
* **Network Heartbeat**: Periodically pings the Kystar KD6 device and fetches hardware statistics.
* **Canvas Renderer**: Dispatches FFmpeg compilation tasks asynchronously.
* **Network Ingestion**: Performs binary file transfers to the media controller without blocking UI draw frames.

### 2. Video Compositing Engine (FFmpeg)
The system leverages FFmpeg for dynamic layout composition. 
* **FPS Constraints**: Rigidly capped at 30 FPS (`_MAX_OUTPUT_FPS` in `src/core/ffmpeg_renderer.py`) to prevent hardware decoder overload on the KD6.
* **Sub-stream Alignment**: Inputs are scaled, padded, and layered via a complex filtergraph, with timestamps normalized using `setpts=PTS-STARTPTS` and frame rates force-aligned using `fps`.
* **Static Assets**: For layouts combining static images and video clips, the renderer uses the `eof_action=pass` parameter in overlay filters. This prevents the output sequence from terminating early when a short video ends.

### 3. API Communication Bridge
The network interface communicates with the Kystar KD6 over HTTP:
* **Identification Protocol**: Before uploading files, the client calculates a custom unique payload identifier: MD5 checksum + File Size. This allows the Kystar hardware to skip redundant uploads.
* **Dynamic Geometry**: Grid geometries are calculated dynamically. The frontend layout is constructed dynamically based on the current parameters of the screen configuration class.

---

## 📚 Manufacturer Documentation

Below is the complete content of the original API and Hardware reference documents.

<details>
<summary><b>Show Technical Documentation (Hardware)</b></summary>

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
</details>

<details>
<summary><b>Show LAN API Documentation (Beijing Kystar)</b></summary>







LAN control interface design
document

## Contents
I.  Revisions  5
-  Purpose of writing  5
3 . Establish connections  5
4 . Return to code description  6
5 . Interface description  7
5.1  Obtain device details  7
5.2  Get the current time/time zone  8
5.3  Get Screen shots  9
5.4  Sync time Information (Sync local time to playback card)   10
5.5  Restart the Playcard   10
5.6  Rename the player card name   11
5.7  Get the status of the Player card (Brightness/Volume/Screen switch status) 12
5.8  Brightness Settings   13
5.9  Setting the automatic brightness adjustment switch  13
5.10  Obtaining the status of the Automatic brightness adjustment switch   14
5.11  Volume Settings   14
5.12  Player card screen on/off   15
5.13  Time Zone Settings   16
5.14  Set the network time  16
5.15  Get the playback status of the player card   17
5.16  Obtain the running time of the Playcard   17
5.17  Obtain the output resolution of the Playcard   18
5.18  Obtain the ip/mac address /sn code of the playcard   18
5.19  Obtain the ram and CPU usage of the player card   19
5.20  Obtain the status of the playback card relay   20
The playback card displays content related (program playback)   20
5.21  Quick program upload   20
5.22  Font file upload   23
5.23  Get the list of font files in the playcard   23
5.24  Get the list of programs in the Playcard   24
5.25  Switching Between Common Programs   27
5.26  Emergency Format switching (Quick switching by program name)   27
5.27  Emergency Text play   28
5.28  Cancel the emergency format and emergency text playback   29
5.29  Change the Playcard control traffic nixie   29
5.30  The Playcard displays text content directly   30
5.31  Playcard directly displays web content   31
5.32  Change the content displayed in the Playcard window   31
5.33  Create or modify the window list   33
5.34  Get the current window of the player card   34
5.35  Delete the player card specified window   35
5.36  Deleting the specified material  36

Advanced publishing (recurring show lists, timed shows, timed instructions, etc.)   37
5.37  Recurring program list publishing   37
5.38  Get the list of recurring shows   38
5.39  Switch the recurring program list to play   38
5.40  Scheduled program playback and release   39
5.41  Get schedule program details   41
5.42  Set the timing of the shims program   42
5.43  Get the Playcard Gasket program   43
5.44  Set the timer play switch   44
5.45  Obtaining the status of the Scheduled play switch   44
5.46  Timing instruction release   45
5.47  Get the list of timing instructions  46
5.48  Set timing instruction switch   47
5.49  Get timing command switch status   47
Player card network related (cable network, WiFi, 4G/5G)   48
5.50  Get the type of network the playcard is currently connected to   48
5.51  Obtain the current ip and DHCP status   49
5.52  Set the wired network to DHCP   50
5.53  Set Wired network to fixed ip   50
5.54  Turn Hotspot on/off   51
5.55  Setting the Hotspot Name, Password, and Channel   51
5.56  Get the hotspot name, Password, Channel   52
5.57  Turn wifi sta on/off   52
5.58  Get the external wifi found by the Playcard   53
5.59  Connect the Playcard to external wifi   53
5.60  Get wifi sta status   54
5.61  Get 4G/5G status   54
5.62  Testing how long it takes the player card to access the network   55
Configure the player card   56
5.63  Setting the Playback card screen rotation   56
5.64  Set the Playback card relay switch  56
5.65  Get the onboard relay Remarks name   57
5.66  Setting the onboard relay Remarks Name   58
5.67  Get the relay Note name of the multi-function card  58
5.68  Set the multi-function card relay note name   59
5.69  Get the sensor value   59
5.70  Obtaining the Player Card Language   60
5.71  Setting the Playcard language  61
5.72  Set the input source HDMI resolution   62
5.73  Get the input source HDMI resolution   62
5.74  Setting the Playback Card Output Crop Area (Local display)   63
5.75  Get the value of the playback card Output Crop area   64
5.76  Setting the Playback card Output Image Scaling (image parameters)   65
5.77  Get the playback card Output image scaling value   65

5.78  Set the player card to restart at a scheduled time   66
5.79  Obtaining the Player card Timed restart status  67
5.80  Delete unused resources from the player card   67
5.81  Restore factory Settings   68
5.82  Restoring the system to factory Settings   68
5.83  Player software version rollback  69
5.84  Get the current signal source mode   69
5.85  Getting the Status of the Player card (Device running status)   70
5.86  Enabling/Disabling Cloud Platform Connection   70
5.87  Setting the Cloud Platform address   71
5.88  Obtaining the status of the Cloud Platform   71
5.89  Obtaining the Cloud Platform Disconnection Detection status   72
5.90  Enabling Cloud Platform Disconnection Detection   72
5.91  Obtaining the Cloud Platform Disconnection Detection time  73
5.92  Enabling Cloud Platform Disconnection Detection   73
5.93  Setting the Sync Playback Function   74
5.94  Get the Sync playback status   74
5.95  Set whether to display the program name when switching programs   75
5.96  Get whether to display the program name when switching programs   75
5.97  Get Playcard logs   76
5.98  Add the Playcard lock password   76
5.99  Get the Player card lock status   77
5.100  Lock the player card   78
5.101  Unlock the Login Playcard   78
5.102  Forgot the Password   78
5.103  Get the send card/receive card information   79
5.104  File screen adjustment   80
5.105  Setting the Network port size of the Player card  81
5.106  USB flash drive broadcast Settings   82
5.107  Get USB flash Drive Live Settings   83
5.108  Set NTP server address   84
5.109  Obtaining the NTP server address   85
5.110  Installing third-party apps   85
5.111  Uninstalling Third-Party Apps   86
5.112  Get the Latitude and longitude of the player card   86
5.113  Text-to-speech broadcast  87
5.114  Stopping Voice broadcast   87
Addendum   89




## I、 Amendments
Content Modification time Who to revise
Create the document for the first time  LYH
4.23 Added scrolling mode for text display  LYH
4.48 Add Quick program release 20231107 LYH
Add  file  screen  adjustment,  set network  port
parameters,  gasket  Settings,  etc.  app  version
must be higher than 602
## 202501104 LYH

II、 Purpose of writing
For the convenience of later function reference and interface debugging, this
description is drafted. This note describes in detail the LAN Settings and access to control
card parameters, related to the hardware and software part of the parameter Settings, for
developers and testers and internal use.
III、 Establishing a connection
1、 Direct connection through IP, used to know the IP of the player card, can directly establish
a connection through IP;
2、 When the player card and the client are in the same LAN, and do not know the IP, you
can directly monitor the broadcast to obtain the list of devices in the LAN, the operation
is as follows:

Receive the broadcast on port 45454, and obtain the source ip address (i.e. the IP address of
the player card) through the broadcast.


"appVersion":"536", // Player app version number
"deviceDetail":"", // Playcard remarks
"Devicedetail ":"KP4H23040652", // Playcard serial number, cannot be modified
"deviceName":"KP4H-23040652", // Player card name, which can be customized
deviceVersion :"Android8.1.0", // Android version number
"ip":"10.10.0.125", // Playcard IP
"model":"KPH", // Playcard type
"screenHeight":572, // screen height
"screenWidth":936, // screen width
"systemVersion":"2.7.8", // System version number
"totalSpace":8192, // Total storage space of player card (unit MB)
"usableSpace":4072, // Remaining space of player card (unit MB)
"usbTotalSpace":0,  //  Total  space  of  external  USB  flash  drive  of  the  player  card  (unit  MB,
external USB flash drive required)
"usbUsableSpace":0,  //  Remaining  space  of  the  external  USB  flash  drive  of  the  player  card
(unit MB, requires an external USB flash drive)
"voice":1.0 // Player card volume (1.0 is 100%)

The player card can be operated after obtaining the IP, port 18080
baseUrl:Http://IP:18080/{request parameter}

If you directly develop the program running in the player card, you can directly use the local
address 127.0.0.1:18080/{Request parameter}
IV、 Return code description
SUCCESS = 200;            // success

FAIL = 501;                   // Failed to send
PARAM_ERROR = 1;    // parameter error
## NOT_FIND = 406;
## URL_ERROR = 404;
## LOGIC_ERROR = 2;
## SERVER_ERROR = 3;

V、 Interface description
For the convenience of testing, each interface has a sample code, can be directly copied to
the browser URL bar access; Or use tools such as postman or Apipost for debugging tests.
5.1 Get Playcard device details
// It will be returned in the broadcast message, usually without a separate request
## Uri Request
method
## Request
parameter
Return value
device GET no {code:xxx,message:xxxxx,
data:{ String ip;
String deviceName;
String groupName;
String absolutePath;
String deviceVersion;
String appVersion;
String systemVersion;
String deviceId;
float voice; (0-1)
int    usableSpace;    (available
space)
int screenWidth;
int screenHeight;
int usbTotalSpace;
int usbUsableSpace;
int broadcastType;
String model; }

Example send data instruction format:
## Http://192.168.0.100:18080/device


Received data processing successful Return example:
## {
"code": 200, // Return value
## "data": {
"appVersion": "272", //app version number
"deviceId": "KP1P21020002", //sn code, serial number
"deviceName": "KP1Proa-21020002", // Device name
"deviceVersion": "2.7.0", // System version number
"model": "KPA", // Device type
"screenHeight": 1080, // Screen height
"screenWidth": 1920, // screen height
"subModel": "KP1Proa", // subdevice type
"systemVersion": "Android8.1.0", // Android version number
totalSpace: 4337, // Total storage space, in MB
"usableSpace": 4146, // Remaining available space, in MB
"usbTotalSpace": 0, // Remaining available space of the USB flash drive (unit MB)
"usbUsableSpace": 0, // Remaining available space of the USB flash drive, unit MB
"voice": 0.8 // Volume value, with 0 to 1,0 being silent and 1 being 100%
## },
"message": "SUCCESS"
## }

5.2 Get the current time/time zone
## Uri Request
method
## Request
parameters
Return value
getCurTime GET no { code:xxx,
message:xxxxx,
curTimeMills: xxxxx,
timeZoneId:xxxx,
isInternetTime :false/true}
Example send data instruction format:

//  Use  the  International  Common  Time  Zone  ID  Comparison  table,  or  see  "Time  Zone
Comparison Table" for details
Http://192.168.0.100:18080/getCurTime

Received data processing successful Return example:
// Current timestamp, whether network time is used, current time zone
## {
"curTimeMills":1665481965589, // time stamp
"isInternetTime":true, // Whether to enable obtaining time from the network, false is disabled
"timeZoneId":"Asia/Shanghai",  //  Time  zone, use  the  international  Time  zone  ID  mapping
table, or see "Time Zone Mapping Table" for details.
## "code":200,
"message":"SUCCESS"
## }

5.3 Get a screenshot
## Uri Request
method
## Request
parameters
Return value
logo //
## Compressed
image
logoRaw //
original image
GET no image/jpeg
Example send data instruction format:
## Http://192.168.0.100:18080/logo

Received data processing successful Return example:
// Screenshot information of the current screen


5.4 Sync time information (Sync local time to playback card)
// Synchronize the local time to the player card, with the network time function enabled, and
the device will use the network time again when the network is reconnected. // If you do not
need to use the network time, use the "Set the network time" to turn off
## Uri Request
method
## Request
parameters
Return value
postCurTime POST Long type
curTimeMills(current
number of
milliseconds)
## {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/postCurTime? curTimeMills=1665481965589

Received data processing success Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }

5.5 Restart playcard
## Uri Request
method
## Request
parameters
Return value

## Reboot
Use   port  number
## 18081
GET no {code:xxx,message:xxxxx}

Example send data instruction format:
## Http://192.168.0.100:18081/reboot

Received data processing successful Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }

5.6 Rename the player card name
// Add a note name to the device, corresponding to the device name in the device details
return value
## Uri Request
method
## Request
parameters
Return value
renameDevice POST String type
deviceName
## {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/renameDevice? deviceName= device name 111

Received data processing success Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }


5.7 Get  Playcard  status  (brightness/volume/screen  switch
status)
// Modify the brightness of the display
## Uri Request
method
## Request
parameters
Return value
getScreenParams GET no {code:xxx,message:xxxxx
int  bright; //  Brightness
## 0-100
float voice; // Volume 0-
## 1
boolean   screenOn;   //
whether   the   screen   is
on}

Example send data instruction format:
// Brightness variable range 0-100, 0 for all black and 100 for highest light
// The volume ranges from 0 to 1, with 0 being silent and 1 being the highest
// Screen switch true is on, false is off
Http://192.168.0.100:18080/getScreenParams

Received data processing successful Return example:
//code:200 The setting is successful
## {
## "bright": 100,
## "contrast": 25,
"screenOn": true, // The screen is on
"screenType": 0, // Generally not used
## "voice": 0.5,
## "code": 200,
"message": "SUCCESS"
## }

## 5.8 Brightness Settings
// Modify the brightness of the display
// To get the current brightness value, see the "Get Player Status" interface
Uri Request mode Request
parameters
Return value
setting/bright POST int type
bright  //0-100
## {code:xxx,message:xxxxx}

Example send data instruction format:
// Variable range 0-100, 0 for all black and 100 for highest light
Http://192.168.0.100:18080/setting/bright? bright=50

Received data processing successful Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }

5.9 Set the automatic brightness adjustment switch
// Automatically adjust the brightness of the screen body according to the ambient brightness
value, only support LED brightness adjustment
// This function needs to be matched with the corresponding brightness sensor peripheral
## Uri Request
method
## Request
parameters
Return value
setAutoBright POST int status;
(Whether to turn
on auto
brightness  1  yes
|0 no)
## {code:xxx,message:xxxxx}

Example send data instruction format:

Http://192.168.0.100:18080/setAutoBright? status=1
// Enable automatic brightness adjustment
Received data processing success Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }

5.10 Get automatic brightness adjustment switch status
// This function needs to be matched with the corresponding brightness sensor peripheral
## Uri Request
method
## Request
parameters
Return value
getAutoBright GET no {code:xxx,message:xxx,
status:xxx} //0 Off 1 On

Example Send data instruction format:
Http://192.168.0.100:18080/getAutoBright
Received data processing successful Return example:
## {
"status": 0, // Auto brightness adjustment is not currently enabled
## "type": 0,
## "code": 200,
"message": "SUCCESS"
## }
5.11 Volume setting
// Modify the volume of the player card
## Uri Request
method
## Request
parameters
Return value
setting/voice POST float type
voice  //0-1
## {code:xxx,message:xxxxx}


Example send data instruction format:
// Variable range 0-1, 0 for silent and 1 for highest
## Http://192.168.0.100:18080/setting/voice? Voice = 0.5

Received data processing successful Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }

5.12 Playcard screen on/off
## Uri Request
method
## Request
parameters
Return value
setting/screen POST boolean
screen
## {code:xxx,message:xxxxx}

Example send data instruction format:
//true indicates that the value is enabled and false indicates that the value is disabled
Http://192.168.0.100:18080/setting/screen? screen=true

Received data processing success Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }


5.13 Time zone Settings
## Uri Request
method
## Request
parameters
Return value
setTimeZoneId POST String
timeZoneId //
Time zone ID
## {code:xxx,message:xxxxx}

Example send data instruction format:
//  Use  the  international  Time  Zone  ID  Comparison  table,  or  see  "Time  Zone Comparison
## Table"
// To  obtain  the  current  time  zone  of  the  player card,  see  the "Get  the  Current  Time/Time
Zone" interface
Http://192.168.0.100:18080/setTimeZoneId? timeZoneId=Asia/Shanghai

Received data processing success Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }


5.14 Set the time to use the network
// On/off The Playcard uses network time, which is on by default
## Uri Request
method
Request parameters Return value
useInternetTime POST int status;
## //0 No. 1 Yes
## {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/useInternetTime? status=1
// Turn on using network time

Received data processing success Return example:
//code:200 The setting is successful
## {
## "code":200,
"message":"SUCCESS"
## }

5.15 Get the playback status of the playcard
## Uri Request
method
## Request
parameters
Return value
getDeviceState GET no {code:xxx,message:xxxxx,
state:xxx,   //1   indicates
that the screen is black. 2
indicates that the
program is playing
programName:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getDeviceState

Received data processing successful Return example:
## {
"programName": "Program 1", // The name of the program currently playing
"state": 2, //1 indicates that the screen is off. 2 indicates that the program is playing
## "code": 200,
"message": "SUCCESS"
## }

5.16 Get the running time of the playcard
## Uri Request
method
## Request
parameters
Return value
getSysRunningTime GET no {code:xxx,message:xxxxx,
runningTime:xxx //
milliseconds}



Example send data instruction format:
Http://192.168.0.100:18080/getSysRunningTime

Received data processing successful Return example:
## {
"runningTime": 135453099, // The unit is ms, and must be converted by itself
## "code": 200,
"message": "SUCCESS"
## }

5.17 Get the output resolution of the playcard
// The resolution size of the system output, generally not set
## Uri Request
method
## Request
parameters
Returned value
getResolution GET no {code:xxx,message:xxxxx,
width:xxx,
height:xxx,
hz:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getResolution

Received data processing successful Return example:
## {
"height": 1080, // Height of output resolution
"hz": 60, // Output frame rate
"width": 1920, // output resolution width
## "code": 200,
"message": "SUCCESS"
## }

5.18 Obtain the ip/mac address /sn code of the player card
Uri Request Request Return value

method parameters
getDeviceDetail GET no {code:xxx,message:xxx,
ip:xxx,
mac:xxx,
id:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/getDeviceDetail

Received data processing successful Return example:
## {
"id": "KP1P21020002", // device sn, unique serial number
ip: 10.10.0.60, // Current ip address
"mac": "fe:5d:bb:13:79:c1 ", // Current device mac address
"wifiMac":"ec:c1:ab:23:ac:db", // Current device WiFi mac address
## "code": 200,
"message": "SUCCESS"
## }

5.19 Get the ram and CPU usage of the playcard
// Run the memory usage and CPU usage
// Added cpu and gpu temperature in version 551
## Uri Request
method
## Request
parameters
Return value
getRunDetail GET no {code:xxx,message:xxx,
freeMem,// Free space
is expressed in kB
totalMem,    //    Total
space in kB
useCpu   //    floating-
point  number  such  as
5.6   indicates   a   cpu
usage of 5.6%}

Example send data instruction format:
Http://192.168.0.100:18080/getRunDetail

Received data processing successful Return example:

## {
"freeMem": 349509, // Free space in running memory, in kB
"totalMem": 976612, // Total running memory space, in kB
"useCpu": 30, // floating-point numbers such as 30 indicate that the cpu usage is 30%
## "code": 200,
"message": "SUCCESS"
## }

5.20 Get the status of the playcard relay
## Uri Request
method
## Request
parameters
Return value
setMultiRelay GET no {code:xxx,message:xxxxx,
status:0~255  //  Change
to 32 bits}

Example send data instruction format:
Http://192.168.0.100:18080/getRunDetail

Received data processing successful Return example:
## {
"freeMem": 349509, // Free space in running memory, in kB
"totalMem": 976612, // Total running memory space, in kB
useCpu: 30, // A floating point number such as 30 indicates that the cpu usage is 30%
## "code": 200,
"message": "SUCCESS"
## }

Playback   card   display   content   related
(program play)
5.21 Quick program upload
This interface supports quick program release and playback, including media upload and
program details upload. Before uploading the program json, ensure that the media used has
been  uploaded,  and  the  program  will  be  played  immediately  after  uploading  the  program

json.

1) Upload media (support resumable resumable)

## Uri Request
method
Request parameters Return value
uploadMedia/{m
ediaType}/{md5
andlength}
POST FILE (multipart)
HEAD(Range:bytes=500-)
Represents the contents of
the section from the 500th
byte to the end of the file
Currently, only this mode is
supported. The HEAD
upload    starts    from    the
zeroth byte by default
(File     upload     must     be
processed, upload from the
500th   byte,   count   from
zero)
## {code:xxx,message:xxx }
uploadMedia/{Material type :1 for video, 2 for image}/{md5AndLength}
md5AndLength is calculated using the following method: If the file is smaller than 1 MB, it
calculates the actual byte size of the md5 connection. If the file is larger than 1 MB, it calculates
the  actual  byte  size  of  the  md5  connection. Such  as:  dddae1f8cb4bdc55b88f6d03edfc6ac2-
## 952324
Calculation method code reference:



action:

## (file)

## =>

## {







let

type

## =

## {

## 'image':

## 2,

## 'video':

## 1

## }[file.type.split('/').shift()];







if

## (!type)

## {









const

extension

## =

file.name.split('.').pop();









type

## =

## {

## 'rmvb':

## 1,

## '3gp':

## 1,

## 'encrypt':

## 1,

## 'kpf':

## 1

## }[extension];







## }







const

size

## =

file.size;







return

new

## Promise((resolve)

## =>

## {









const

reader

## =

new

FileReader();









reader.readAsArrayBuffer(file);









reader.onload

## =

## (e)

## =>

## {











const

bit

## =

e.target.result.slice(0,

## 1024

## *

## 1024);











const

md5

## =

new

SparkMd5.ArrayBuffer();











md5.append(bit);











const

upUrl

## =

(`http://${window.global.deviceIP}/uploadMedia/${type}/${md5.end()}
## -
## ${size}`);











resolve(upUrl);









## }







## })





## }



2) Check if the media has been uploaded // Before uploading the material media you

can check if it exists on the device
## Uri Request
method
Request parameters Return value
checkUpload POST String md5andlength {code:xxx,message:xxxxx}
Code 200 has been
uploaded
The Code 406 file does not
exist

3) Get the material list // Get all the material in the terminal can be used for program
editing, existing material can be used without uploading, directly use md5 and type
## Uri Request
method
## Request
parameters
Return value
medias GET no
## {
## "code":200,
## "data":[
## {
## "duration":59233,
## "height":1080,
"isMainView":false,

"md5AndLength":"ecf274cb82a53a38ee12a4b7a69e5b8
a-63389739",
## "name":"test.mp4",
## "size":63389739,
## "type":1,
## "width":1920
## }
## ],
"message":"SUCCESS"
## }


4) Upload  quick  program  json  //  Only  support  picture  and  video  list  playback; After
successful upload, the device will immediately play the changed program
## Uri Request
method
Request parameters Return value
uploadThirdP
rogram
POST "name": "test", // program name
"width": 500, // program width, in px
"height":  500,  //  The  height  of  the  program,  in
px, is the default screen size
"mediaList": [
## {
"Md5AndLength" : "3
cb4852c4cb2c624341188223f83195c -
3884675", / / material MD5 + file size bytes,
## "duration":   10000,    //    Playback
duration, in milliseconds. The video is the actual playback
duration, and the image duration can be specified.
## {code:xxx,mess
age:xxx }

"anim":    "CA_CHU" //     Special
effects,  special  effects  corresponding  table,  please  refer
to the attachment description.
## },
## {
"md5AndLength":
## "af37b81f222df53df341b5895ab1a71c-
## 26472",
## "duration": 10000,
"anim": "CA_CHU"
## }
## ]
## }


5.22 Font file upload
## Uri Request
method
Request parameters Return value
uploadText/{en
Name}/{chName
}/{fileLength}
POST enName //  English  name,
use this value for uploading
shows
chName  //  Chinese  name,
the  name  of  the  font  used
to show the user
fileLength  //  Actual  size  of
the font file, in bytes
## {code:xxx,message:xxx }


5.23 Gets a list of font files in the playcard
## Uri Request
method
Request parameters Return value
getTextStyle GET no {code:xxx,message:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/getTextStyle

Received data processing successful Return example:
## "code": 200,
## "data": [
## {
"chName": "drivelight", // display name
"enName": "drivelight", // name id, used to transfer programs
"fileLength": 69616,
## "path": "/storage/emulated/0/kystar/commander/server/text_style/drivelight"
## },
## {
"chName": "quicksand",
"enName": "quicksand",
"fileLength": 106468,
## "path": "/storage/emulated/0/kystar/commander/server/text_style/quicksand"
## },
## ],
"message": "SUCCESS"
## }

5.24 Get the list of programs in the playcard
## Uri Request
method
## Request
parameters
Return value
programs GET no {code:xxx,
message:xxxxx
data:[](program array)}
programsSimple
// This interface returns value
content  concise,  try  to  use
GET no {code:xxx,
message:xxxxx
data:[](program array)}

this

Example format of send data instruction:
Http://192.168.0.100:18080/programsSimple

Received data processing successful Return example:
## {
## "code": 200,
## "data": [
## {
## "height": 1080,
"id": "d44f618e-5a56-4fea-af0b-2bd86be2be8e", // Program id
"isDefault": false,
"isUsbProgram": false,
"name": "program-5 ", // program name
"notPlay": false,
## "order": 0,
"play": true,
"playTime": 10800,
"screenHeight": 0,
"screenWidth": 0,
"shouldCopy": false,
"tempPlayCount": 0,
"tempPlayTime": 0,
## "thumb": "d44f618e-5a56-4fea-af0b-2bd86be2be8e",
## "width": 1920
## },
## ]
"message": "SUCCESS"
## }


5.25 Gets a recurring playlist from the playcard
## Uri Request
method
## Request
parameters
Return value
programSheetList GET no {code:xxx,
message:xxxxx
data:[](program array)}

Example format of send data instruction:
Http://192.168.0.100:18080/programSheetList

Received data processing successful Return example:
## "code": 200,
## "data": [
## {
"id": "37d910e3-ce2d-4b8c-a272-b0e5d01c2595", // id of the loop list, which
is used for switching playback
"isDefault": false,
"isUsbProgram": false,
"name": "Loop play 1",
"play": true,
"playCountList": [
## 1,
## 1
## ],
"playTimeList": [
## 6000,
## 6000
## ],
"programlist": [Program list
## ]
## }
## ],
"usePlayTimeList": [
## 0,
## 0
## ],
## "version": 0
## }
## ],
"message": "SUCCESS"

## }
5.26 Toggle play
// Use the program id to toggle playback
// Also use this interface if you need to switch to a circular playlist
## Uri Request
method
Request parameter Return value
program/play POST String id;
//  program  id,  obtained  from  the
program list
## {code:xxx,messag
e:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/program/play? id=d44f618e-5a56-4fea-af0b-2bd86be2be8e

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.27 Emergency  format  switching  (quick  switching  by  show
name)
// Call the program directly through the program name to play, usually used for emergency
quick display, you must ensure that the name of the program in the playback card
// This display mode is to directly cover the original program. There may be video playback
in  the  original  program,  and  there  may  be video  hierarchy  error  in  the  switched  program.
Therefore, emergency format programs should use the graphic format as far as possible.
## Uri Request
mode
Request parameters Return value
programPlayBy
## Name
POST String programName;
// program name
## {code:xxx,messag
e:xxxxx}
Example send data instruction format:
Http://192.168.0.100:18080/programPlayByName? programName= Program 1

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"

## }

5.28 Emergency text play
// Quickly send an emergency text message and play it suspended at the top of all layers
// This interface requires a special playcard version
## Uri Request
method
Request parameters Return value
sendTextInfo
## POST
String playTime //
Playback     duration,     in
milliseconds
## ...
## {code:xxx,
message:xxx }


Example send data instruction format:
http://10.10.0.129:18080/sendTextInfo?playTime=100000&playRank=1&text=5662652122&
bgColor=0&textColor=65536&textSize=200&
scrollDir=5&scrollSpeed=5&turnPageTime=3000&bgMd5AndLength=bf32009db8a822046
27c2aa305c43ca6453105&x=0&y=0&width=1920&hei ght=1080&mute=1

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.29 Unblock emergency format and emergency text playback
// Can remove the currently playing emergency format and text
## Uri Request
method
## Request
parameters
Return value
cancelTextInfo GET no { code: 200,
"message": "SUCCESS"}
Example send data instruction format:
Http://10.10.0.126:18080/cancelTextInfo

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.30 Change the Playcard control traffic nixie
// Hardware IO controls the nixie display, a custom system version is required
## Uri Request
method
Request parameters Return value
playNum POST String textNum;
//1r2y3b4g indicates that from left
to  right  the  first  number  is:  red  1
The  second  number  is:  yellow  2
The third number is: not displayed
the fourth number is: green 4;
//    Two    characters    identify    a
number that is displayed, r  is red,
g  is  green,  y  is  red,  and  b  is  not
displayed
//   The   number   of   groups   of
numbers  in  an  induction  screen
can be transmitted
## {code:xxx,messag
e:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/playNum? textNum=1r2y3b4g


Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.31 The playcard displays the text content directly
// Automatically cancels the current program and plays the uploaded text content directly on
the screen
## Uri Request
method
Request parameters Return value
playText POST String    text;          //    text
content %0A is line feed
int  width;    //  Specify  the
width   and   height   within
which  the  text  will  appear,
centered by default in px
int height;
int scrollSpeed;  //
## Scrollspeed, 1-9
int  color;      //  Text  color
0xff_ffffff  argb  format  such
as -1==0xff_ffffff  indicates
white
-65536==0xff_ff0000 red
## -16711936==0xff_00ff00
## Green
Convert    to    signed    bit
decimal, calculation
method  refer  to  "Pandora
## Color Conversion Tool"
int  scrollDir;  //0
stationary,  1  from  left  to
right, 2 from right to left, 3
from top to bottom, 4 from
bottom to top
int textSize ;   // font size in
px
## {code:xxx,messag
e:xxxxx}


Example send data instruction format:
Http://192.168.0.100:18080/playText? text= Sample text display &width=512&height=64&
scrollSpeed=2&color=-1&scrollDir=1&textSize=50

Add a newline character "%0A" to the text if you need a newline
Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.32 The playcard displays the web page content directly
// Can play the uploaded webpage link directly on the screen
## Uri Request
method
Request parameters Return value
playWeb POST String  url;     //  web  page
link, such as
https://www.baidu.com
int  width;    //  Specify  the
width   and   height   within
which  the  text  will  appear,
centered by default in px
int height;
## {code:xxx,messag
e:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080 / playWeb?
url=https://www.baidu.com&width=512&height=256
Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.33 Change what the playcard window displays
// The content of different Windows on the screen can be changed. The number of Windows
needs to be confirmed during deployment and released to the playcard. The following only
describes the changed content.
Uri Request Request parameters Return value

method
changeWindow POST String index;  //
Window serial number
String  type;   //  Text  to
## 20
String  property;   //  1
video, 2 pictures can not
be  transferred  to  other
required  (converted  to
json string)
## }
## }
## {code:xxx,messag
e:xxx }

Property note
## {
"offsetY":3,    //
"shaderStyle":0, // Color word style, 0-8, 0 is no style, this time 0
"text":"12115455", // Text content
"backgroundColor":0,
"halign":1, // alignLeft = 1; alignRight = 2; alignHcenter = 4;
"valign":32, // alignTop = 32; alignBottom = 64; alignVcenter = 128;
"isLoop":true, // end to end when scrolling
"scrollDirection":0, // Display mode, 0 at rest, 1 from left to right, 2 from right to left, 3 from
top to bottom, 4 from bottom to top, 5 turn the page
"scrollSpeed":3, // Scrolling speed
"textColor":-1, // Text color argb format such as -1==0xff_ffffff for white -65536==0xff_ff0000
red -16711936==0xff_00ff00 Green; JAVA int value with sign bit, calculation method can refer
to the "Pandora color Converter" gadget.
// Alternatively, the hexadecimal color value can be directly converted to an int value, such
as: 0x409EFF = 64*65536+158*256+255
"textStyle":0,    //
"turnPageTime":5000," // Page turning time
"enName":" ", font style, do not pass default "Microsoft Yahei"
"textSize":278," // Text size, in px
## }

Example send data instruction format:
10.10.0.108:18080 / changeWindow?
index=0&type=20&Property={"offsetY":3,"shaderStyle":0,"text":"123","backgroundColor":0,"
halign":1,"textColor":-65536,"va lign":32,"enName":"","textSize":278}
Sample return of received data:

## {code:xxx,message:xxx }

5.34 Create or modify the window list
//  You  can  freely  create  Windows  on  the  screen  through  this  interface,  the  content  of  the
newly created window is empty, you need to cooperate with the "Change the display content
of the player card window" interface to increase the display content;
// This interface creates a window according to the index serial number. If there is this serial
number window on the original screen, it will be replaced directly. If there is no window, it will
be added;
//index start count is 0, if there is only one window on the screen, but the new index is 5, then
the player card will be added to the default index is 1.
## Uri Request
method
Request parameters Return value
setWindows POST json   //   window   detail
description
## [
## {
## "index": 0,
## "x": 0,
## "y": 0,
## "w": 512,
## "h": 512
## },
## {
## "index": 1,
## "x": 512,
## "y": 0,
## "w": 512,
## "h": 512
## }
## ]
## {code:xxx,messag
e:xxx }




Data note
## [
## {
"index": 0, // window serial number, starting with 0
"x": 0, // the horizontal position of the window in px
"y": 0, // the vertical position of the window, in px
"w": 512, // the width of the window, in px
"h": 512 // the height of the window, in px
## },
## {
## "index": 1,
## "x": 512,
## "y": 0,
## "w": 512,
## "h": 512
## }
## ]
5.35 Gets the playcard current window
// All window properties on the current screen of the player card can be obtained through
this interface, including the number and position size.
## Uri Request
method
## Request
parameters
Return value
curWindows GET no {code:xxx,message:xxxxx,
data:xxx,  //  window  size
position}


Example send data instruction format:
Http://192.168.0.100:18080/curWindows

Received data processing success Return example:
## {
## "code": 200,
## "data": [
{// The following is the window order, sorted from 0, the first one corresponds to
index=0 in the "Change what the Playcard window displays" interface
"x": 0, // horizontal coordinate
"width": 448, // wide
"y": 0, // horizontal coordinate
"height": 512 // height
## }
## {
"x": 448, // horizontal coordinate
"width": 448, // wide
"y": 0, // horizontal coordinate
"height": 512 // height
## }

## ],
"message": "SUCCESS"
## }

5.36 Delete the playcard specified window
## Uri Request
method
Request parameter Return value
delWindows POST json; // window
serial number
## {code:xxx,message:xxxx
x}
## // Success 200

Example send data instruction format:
// Delete 1,2 Windows of the current screen of the player card


Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.37 Delete specified material
## Uri Request
method
## Request
parameters
Returned value
deleteMedia POST String
md5AndLength;
## {code:xxx,message:xxxx
x}
//  Success  200,  failure
501  (count  as  material
in use)

Example send data instruction format:
Http://192.168.0.100:18080/deleteMedia?  md5AndLength={Gets  the md5AndLength  of  the
material through the interface that gets the terminal material}

Received data processing success return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

Failed to receive data processing Return example:
## {
"code": 501, // The current footage is in use and cannot be deleted
"message": "SUCCESS"
## }


Advanced  publishing  (recurring  program
lists, timed  programs, timed  instructions,
etc.)
5.38 Recurring program list publishing
//  Support  the  playback  card  to  play  multiple  programs,  and  support  to  set  the  playback
duration or playback times of each program
## Uri Request
method
## Request
parameters
Return value
uploadProgramSheet POST
file
## {code:xxx,message:xxx }

Example send data instruction format:

## {
"id":"f27978a9-8b25-4610-bb39-c672e74a4a1b", // Cyclic list UUID, self-generated
"name":" Loop Play 4", // loop list name, for display
"playCountList":[
## 2,
## 1
], // Number of plays
"playTimeList":[
## 10000,
10000 // Play time, time unit milliseconds
## ],
"usePlayTimeList":[
## 0,
0 // Whether to use time play

## ],
programScreenIds:  "[\"54d3d626-9d5a-4c40-8ef2-94df5afff870\",\"0c998f9a-1f6e-4ff5-bddb-abf0692b9268\"]"  //  Two
program ids of the loop list, which can be read back from the device programs
## }


Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.39 Get a list of recurring shows
// Support  the  playback  card  to  automatically execute  the  command  content  according  to
the set time
## Uri Request
method
## Request
parameters
Return value
programSheetList GET no {code:xxx,message:xxxxx,
data:[List 1, List 2]}

Example send data instruction format:
Http://192.168.0.100:18080/programSheetList

Received data processing successful Return example:


5.40 Toggle loop program list playback
// Support the playback card to quickly switch to a pre-stored cyclic list according to the id;
// With the ordinary program switch playback interface

## Uri Request
mode
Request parameters Return value
program/play POST String id The id of the loop list
or show, available from
programSheetList
## {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/program/play? id=54d3d626-9d5a-4c40-8ef2-94df5afff870
// The id of the loop list or show, available from programSheetList or programsSimple.

Received data processing success Return example:
## {
"code":200,"message":"SUCCESS"
} // Note: Cannot switch when the playcard is playing a timed program. The return value
is as follows {"code":1000,"message":" Timed playback is enabled and cannot be switched "}

5.41 Timed program playback is published
// Support the playback card to automatically play corresponding programs according to the
set time
//  Support  playback  period  setting,  consecutive  playback  times,  effective  date  and  week
setting
// After the release is complete, the player card will play at this time immediately
## Uri Request
method
Request parameters Return value
uploadSchedule POST
file
## {code:xxx,messag
e:xxx }

Example send data instruction format:


## [
## {
"action": 1, //1 indicates the timed program playback property
"allNumber": 0, // Total number of plays. 0 indicates unlimited plays. Other values are actual plays
"dateEnd": "2024/08/12", // end play date
"dateStart": "2024/08/12", // start date
"defaultValue": 0,
"endTime": "23:59:59", // End playback time
## "id": "0c998f9a-1f6e-4ff5-bddb-abf0692b9268",
"isDateLimit": true, // Whether date limit true indicates limit, false indicates no limit
"isWeekLimit": true, // Whether the week limit is true and false is unrestricted
"level": 1, // level, do not pass
"name": "Program 2", // program name
"playCount": 1, // Number of consecutive plays, default 1
"startTime": "00:00:00", // Start time for playback
"validWeek": 14, // Valid week. If the value is 1110 after binary conversion, Monday, Tuesday, and Wednesday
are limited. For example,  0b1010010 has seven digits in total, numbered from right to left. The first  digit is Sunday, the
second digit is Monday, the third digit is Tuesday, and so on, that is, Monday, Thursday, and Saturday are valid weeks.
"value": 0 // The default value is 0
## },
## {
## "action": 1,
"allNumber": 0,
"dateEnd": "2024/08/19",
"dateStart": "2024/08/19",
"defaultValue": 0,
"endTime": "23:59:59",
## "id": "54d3d626-9d5a-4c40-8ef2-94df5afff870",
"isDateLimit": false,
"isWeekLimit": false,
## "level": 1,
"name": "Program 1",
"playCount": 1,
"startTime": "00:00:00",
"validWeek": 0,
## "value": 0
## }
## ]
User interface reference design


Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.42 Get timed program details
// Playcards support only one timed playlist
// Timed playlist configurable switch
## Uri Request
mode
## Request
parameters
Return value
getScheduleList GET no {code:xxx,message:xxxxx,

data:[List 1, List 2]}

Example send data instruction format:
Http://192.168.0.100:18080/getScheduleList

Received data processing successful Return example:
## {
## "code": 200,
## "data": [
## {
"action": 1, //1 indicates the timed program playback property
"allNumber": 0, // Total number of plays. 0 indicates unlimited plays. Other values are actual plays
"dateEnd": "2024/08/12", // end play date
"dateStart": "2024/08/12", // Start date
"defaultValue": 0,
"endTime": "23:59:59", // End playback time
## "id": "0c998f9a-1f6e-4ff5-bddb-abf0692b9268",
"isDateLimit": true, // Whether date limit true indicates limit, false indicates no limit
"isWeekLimit": true, // Whether the week limit is true and false is unrestricted
"level": 1, // level, do not pass
"name": "Program 2", // program name
"playCount": 1, // Number of consecutive plays, default 1
"startTime": "00:00:00", // Start time for playback
"validWeek": 14, // Valid week. If the value is 1110 after binary conversion, Monday, Tuesday, and Wednesday
are limited. For example,  0b1010010 has seven digits in total, numbered from right to left. The first  digit is Sunday, the
second digit is Monday, the third digit is Tuesday, and so on, that is, Monday, Thursday, and Saturday are valid weeks.
"value": 0 // The default value is 0
## },
## {
## "action": 1,
"allNumber": 0,
"dateEnd": "2024/08/19",
"dateStart": "2024/08/19",
"defaultValue": 0,
"endTime": "23:59:59",
## "id": "54d3d626-9d5a-4c40-8ef2-94df5afff870",
"isDateLimit": false,
"isWeekLimit": false,
## "level": 1,
"name": "Program 1",
"playCount": 1,
"startTime": "00:00:00",
"validWeek": 0,
## "value": 0
## }
## ],
"message": "SUCCESS"
## }

5.43 Set a timer to play the shims program
// Set a spacer in the timing schedule of the playcard, and play the spacer automatically when
there is no time in the schedule;
// gasket follow the timing play, when the timing play is closed, the gasket program does not
take effect at the same time;

// gasket: also become the base map, in the scheduled playback, for the set time of the section,
will be filled with this gasket to ensure that the screen is not black screen.
## Uri Request
method
## Request
parameters
Return value
setUnderlayProgram
POST String   name   //
program  name,
cancel  gasket  if
empty   or   not
passed
## {code:xxx,message:xxxxx,
## }

Example send data instruction format:
Http://192.168.0.100:18080/setUnderlayProgram? name= Program 1

Received data processing success Return example:
## {
## "code": 200,
"isRunning": false,
"message": "SUCCESS"
## }

5.44 Get the playcard Gasket program
// Support to get the switch status of the playback card timing program playback
## Uri Request
method
## Request
parameters
Return value
getUnderlayProgram GET no {code:xxx,message:xxxxx,
"data" : "Program 1" // program
name}

Example format of send data instruction:
Http://192.168.0.100:18080/getUnderlayProgram

Received data processing successful Return example:
## {
## "code": 200,
"data": "Program-27 ", // The current gasket program is program-27
"message": "SUCCESS"
## }


5.45 Set the timed play switch
// Set the switch of timing program playback on the player card
## Uri Request
method
## Request
parameters
Return value
scheduleRunning
## GET
Boolean isRunning
//true    indicates
on, false indicates
off
## {code:xxx,message:xxxxx,
## }

Example send data instruction format:
Http://192.168.0.100:18080/scheduleRunning? isRunning=true

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.46 Get timed play switch status
// Support to obtain the switch status of the timed program playback card
## Uri Request
method
## Request
parameters
Return value
isScheduleRunning GET no {code:xxx,message:xxxxx,
isRunning": true //true indicates on,
false indicates off}

Example send data instruction format:
Http://192.168.0.100:18080/isScheduleRunning

Received data processing successful Return example:
## {
## "code": 200,
"isRunning": false, // Timed playback is off
"message": "SUCCESS"
## }



5.47 Timed instruction release
// Support  the  playback  card  to  automatically execute  the  command  content  according  to
the set time
// Support brightness, volume, switching relay, switching screen, signal source switching, etc
//action Value description: brightness adjustment -- 2, volume adjustment -- 3, off screen -
- 4, on screen -- 5, signal source switching -- 6, relay off -- 7, relay on -- 8
## Uri Request
method
## Request
parameters
Return value
uploadSettingSchedule POST
file
## {code:xxx,message:xxx }

## Fields Type Instructions
action int 1 is the program switch, 2 is the brightness adjustment, 3 is the volume
adjustment, 4 is the screen off, 5 is the screen on, 6 is the signal source
switch, 7 is the relay off, 8 is the relay on
name String Action if 1 is the program or loop name
value int The value of Action if it is not 1
Action is when the signal source is switched (AUTO = 1; ANDROID = 2; HDMI
## = 3;)
Action when 7 or 8 (0b11111111 binary means all selected)
startTime String Operation start time (format HH:mm:ss)
endTime String End of operation time (format HH:mm:ss)
isDateLimit boolean Whether there is a date limit
isWeekLimit boolean Whether there is a week limit
dateStart String Date limit start time (format yyyy/MM/dd)
dateEnd String End time of date limit (format yyyy/MM/dd) Box automatically adds 24 hours
validWeek int Valid weeks such as 0b1010010 There are seven, from right to left, the first is
Sunday, the second Monday, the third Tuesday, and so on that Monday,
Thursday, Saturday are valid weeks
playCount int Number of plays of the program when Action is 1
id String Action indicates the program ID when 1

Example send data instruction format:


Received data processing successful return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.48 Get a list of timing instructions
// Support the playback card to automatically execute the instruction content according to
the set time
## Uri Request
method
## Request
parameters
Return value
getSettingScheduleList GET no {code:xxx,message:xxxxx,
data:[List 1, List 2]}

Example send data instruction format:
Http://192.168.0.100:18080/getSettingScheduleList

Received data processing successful Return example:
## {
## "code": 200,
## "data": [
## {
## "action": 2,
"allNumber": 0,

"dateEnd": "2024/08/18",
"dateStart": "2024/07/25",
"defaultValue": 0,
"isDateLimit": true,
"isWeekLimit": true,
## "level": 1,
"name": "Brightness Adjustment ",
"playCount": 1,
"startTime": "09:29:19",
"validWeek": 62,
## "value": 80
## },
## ]
"message": "SUCCESS"
## }

5.49 Set the timing command switch
// Set the switch of the timing instruction of the playback card
## Uri Request
method
## Request
parameters
Return value
settingScheduleRunning
## GET
Boolean isRunning
//true    indicates
on, false
indicates off state
## {code:xxx,message:xxxxx,
## }

Example send data instruction format:
Http://192.168.0.100:18080/ScheduleSettingRunning? isRunning=true

Received data processing success Return example:
## {
## "code": 200,
"isRunning": false,
"message": "SUCCESS"
## }


5.50 Get timing instruction switch status
// Support to get the timing instruction status of the current playback card

## Uri Request
method
## Request
parameters
Return value
isScheduleSettingRunning GET no {code:xxx,message:xxxxx,
isRunning": true //true indicates
on, false indicates off}

Example send data instruction format:
Http://192.168.0.100:18080/isScheduleSettingRunning

Received data processing successful Return example:
## {
## "code": 200,
"isRunning": false,
"message": "SUCCESS"
## }



Playcard  network  related  (Wired,  WiFi,
## 4G/5G)

5.51 Get   the   type   of network   the   playcard   is   currently
connected to
// This interface can obtain the network type and ip of the current connection

## Uri Request
method
## Request
parameters
Return value
getNetInfo GET no {
## "code": 200,
## "data": {
## "ip": "10.10.0.106",
## "type": "1"
## },
"message": "SUCCESS"
## }

type 1 Cable network
type is 2 WiFi connection
type is 3 4G/5G mobile network


Example send data instruction format:
Http://192.168.0.100:18080/getNetInfo

Received data processing successful Return example:
## {
## "code": 200,
## "data": {
## "ip": "10.10.0.106",
"type": "1" // Wired network connection
## },
"message": "SUCCESS"
## }

5.52 Get the current ip and DHCP status
// Get the ip of the device, gateway, subnet mask, and whether the ip status is automatically
obtained
## Uri Request
mode
## Request
parameters
Return value
getNetState GET no {code:xxx,message:xxxxx,
state:0
ip:xx,
mask:xxx,
gateway:xxx
## }
state is 1 static IP
state is 0 to automatically obtain an IP

Example send data instruction format:
Http://192.168.0.100:18080/getNetState

Received data processing successful Return example:
## {
gateway: 10.10.0.1,
ip: "10.10.0.137",
## "mask": "255.255.0.0",

"state": 0, //DHCP automatically obtains an ip address
## "code": 200,
"message": "SUCCESS"
## }

5.53 Set wired network to DHCP
// Set your playcard's wired network to automatically get ip
## Uri Request
method
## Request
parameters
Return value
setAutoIp GET no {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/setAutoIp

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.54 Set wired network to fixed ip
// Fix the playcard's wired network to a fixed ip address
## Uri Request
method
Request parameters Return value
setStaticIp POST String ip (ip address)
String mask(subnet mask)
String gateway(gateway)
String   dns(Optional.   The
default is 114.114.114.114)
## {code:xxx,message:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/setStaticIp? IP = 192.168.0.123 & mask = 192.168.0.1 & gateway
## = 255.255.255.0 & DNS = 114.114.114.114

Received data processing successful return example:
## {
## "code": 200,
"message": "SUCCESS"

## }

5.55 Turn hotspot on/off
## Uri Request
method
Request parameters Return value
setWifiApOpen POST int status;
//0 off 1 On
## {code:xxx,message:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/setWifiApOpen? status=1

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.56 Set the hotspot name, password, channel
// The wired network that will play the card fixes an ip address
## Uri Request
method
## Request
parameters
Return value
setWifiAp POST no String name
String    password    //    At    least    8
characters
int channel (1-13)

Example send data instruction format:
Http://192.168.0.100:18080/setWifiAp?
name=AP123456&password=88888888&channel=11

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.57 Get the hotspot name, password, channel
## Uri Request
method
## Request
parameters
Return value
getWifiApState GET no {code:xxx,message:xxxxx,
name:xxx,
password:xxx,
isOpen:false/true,(open or not)
channel:1-13 (channel)}

Example send data instruction format:
Http://192.168.0.100:18080/getWifiApState

Received data processing successful Return example:
## {
## "channel": "11",
"isOpen": true,
"name": "KP4H-21061256",
## "password": "88888888",
## "code": 200,
"message": "SUCCESS"
## }

5.58 Turn wifi sta on/off
## Uri Request
method
Request parameter Return value
setWifiOpen POST int status;
//0 off 1 On
## {code:xxx,message:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/setWifiOpen? status=1

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.59 Get the external wifi that the playcard searched for
## Uri Request
method
Request parameters Returned value
getWifiNameList GET no {code:xxx,message:xxx
data:[wifi name]}

Example format of send data instruction:
Http://192.168.0.100:18080/getWifiNameList

Received data processing successful Return example:
## {
## "code": 200,
## "data": [
"TP-LINK_kommander", // The signal is arranged from strong to weak
## "p2",
"Openwrt_2. 4 g",
## "MERCURY_B3E6",
## "KPB-5FILTI8R",
## "YQHZ",
## "KP1-21034516",
## "YQHZ",
"KP1Proa-21010999"
## ],
"message": "SUCCESS"
## }

5.60 The playcard connects to external wifi
## Uri Request
method
Request parameters Return value
wifiConnect POST String name // Name
String password //
## Password
## {code:xxx,message:xxx }

// Wired network sequence: wired network -- wifi -- 4G/5G mobile network; Can not access
the wifi network connection when the cable network connection
Example send data instruction format:
Http://192.168.0.100:18080/wifiConnect? name=wifi123&password=88888888
// wifi and password of the router you want to connect to


Received data processing successful return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.61 Get wifi sta status
// Switch status and whether it is connected to an external hotspot, and the name of the
hotspot
## Uri Request
method
## Request
parameters
Return value
getWifiState GET no {code:xxx,message:xxxxx,
name:xxx,
password:xxx
isOpen:false/true    (open    or
not)}

Example send data instruction format:
Http://192.168.0.100:18080/getWifiState

Received data processing successful Return example:
## {
"isOpen": true,
"name": "", // Empty indicates that you are not currently connected to an external hotspot
## "password": "",
## "code": 200,
"message": "SUCCESS"
## }
5.62 Get 4G/5G status
// Supporting device: 4G/5G module is required
## Uri Request
method
## Request
parameters
Return value
get4GDetail GET no {code:xx,message:xxx,data:{
String provider;    // Provider
String  celluarType;  //  Network
type
private   int   level;      //   Signal
strength

private   int   dbm;      //   Signal
strength
private   int   asu;        //   Signal
strength
private  int  state;  //0  indicates
that   there   is   no   4G   module,   1
indicates that no SIM card is inserted,
and  2  indicates  that  the  SIM  card  is
inserted
private String ip; //ip address
## }}

Example send data instruction format:
Http://192.168.0.100:18080/get4GDetail

Received data processing successful Return example:
## {
## "code": 200,
## "data": {
## "asu": 50,
## "dbm": 100,
## "level": 2,
## "state": 2
## },
"message": "SUCCESS"
## }

5.63 Test playcard access to the network takes time
// Can access a website and receive the return code of the website to judge the networking
status of the player card, and can be used to check the network environment of the current
connection of the player card
## Uri Request
method
Request parameters Return value
testHttp POST String url
//  Full  path  to  the  website
such as:
https://www.baidu.com
## {code:xxx,message:xxx,   {code:
XXX,message: XXX,
responseCode,(website  return
code  0  indicates  connection
failure, other   refer   to   http
protocol)
useTime; (in milliseconds)}


Example send data instruction format:
Http://192.168.0.100:18080/testHttp? url=https://www.baidu.com

Received data processing successful Return example:
## {
"responseCode": 200, // return code, when 0, access times out
"useTime": 371, // Connection time 371ms, you can determine the network connection
speed
## "code": 200,
"message": "SUCCESS"
## }
Play card related configuration
5.64 Set the playback card screen rotation
// Supports rotation of 0,90,180,270 degrees, currently only applicable KP2K/KP4K
## Uri Request
method
Request parameters Return value
screenRotate POST int
angle; / /
## 0/90/180/270
## {code:xxx,message:xxx
xx}

Example send data instruction format:
Http://192.168.0.100:18080/screenRotate? angle=90 // Rotates the display output screen by
90 degrees

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.65 Set the playcard relay switch
## Uri Request
method
Request parameters Return value
setAllRelay POST int status (12 bits)
int isOpen (0/1)
## {code:xxx,message:xxx
xx}


// For example, status=4095 (0b111111111111), each bit indicates one relay, and the
corresponding bit is 1, indicating the relay to be controlled.
// isOpen=1, indicating that the relay selected in status is set to the on state, 0 is set to the
off state
## // 0b   1          1   1   1                  1   1   1   1   1   1   1   1



Example send data instruction format:
Http://127.0.0.1:18080/setAllRelay? status=1664&isOpen=1
## //1664==0b0 110 1000 0000
// Turn on circuit 8 of the multi-function card and circuit 2,3 of the on-board relay
Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.66 Get onboard relay note name
## Uri Request
method
## Request
parameters
Return value
getPx30RelayName GET no {code:xxx,message:xxxxx,
data:[Name 1, name 2...] }

Example send data instruction format:
Http://192.168.0.100:18080/getPx30RelayName

Received data processing successful Return example:
## {
## "code": 200,
## "data": [
"1, switch 1", // First relay Note Name switch 1
"2, switch 2",
"3, switch 3"
## ],
"message": "SUCCESS"
## }

External multi-function card,
corresponding 1-8 lines from right to
left
Onboard relay,
From right to left
corresponding 1-3
way
KPB12 relay

5.67 Set the onboard relay note name
## Uri Request
method
Request parameters Return value
setPx30RelayName POST relayName:xxx   (string
array to JosnString)
//    Note    that    the
current    relay    serial
number must be
added before the user
input string by default.
Refer  to  the  obtained
relay name
## {code:xxx,message:xxxxx}
// Note names can be set for three on-board relays

Example send data instruction format:
Http://192.168.0.100:18080/setPx30RelayName? relayName= ["1, air conditioner ","2, switch
2","3, switch 3"]

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.68 Get the relay note name for the multifunction card
## Uri Request
method
## Request
parameters
Return value
getRelayName GET no {code:xxx,message:xxxxx,
data:[Name 1, name 2...] }

Example send data instruction format:
Http://192.168.0.100:18080/getRelayName

Received data processing successful Return example:
## {
## "code": 200,
## "data": [

"1, switch 1",
"2, switch 2",
"3 switch 3",
"4, switch 4",
"5, switch 5",
"6, switch 6",
"7, switch 7",
"8, switch 8"
## ],
"message": "SUCCESS"
## }
5.69 Set the multi-function card relay note name
## Uri Request
mode
Request parameters Return value
setRelayName POST relayName:xxx   (string
array to JosnString)
//    Note    that    the
current    relay    serial
number must be
added before the user
input string by default.
Refer  to  the  obtained
relay name
## {code:xxx,message:xxx
xx}
// Note name can be set for eight on-board relays

Example send data instruction format:
Http://192.168.0.100:18080/setRelayName? RelayName = "1, air conditioning", "2, switch 2",
"3, switch 3", "4, computer", "5, fan", "6, switch", "7, switch 7", "eight, switch 8"]

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.70 Get the sensor value
// Support to get brightness/temperature/humidity/smoke values
// Required hardware module support

## Uri Request
method
## Request
parameters
Return value
getSensorInfo GET no {
## "bright": 834,
"ppm": -1000,  (-1000  means  the
device is not plugged in)
## "temp": 25.8,
## "wet": 74.6,
## "code": 200,
"message": "SUCCESS"
## }

Example send data instruction format:
Http://192.168.0.100:18080/getSensorInfo

Received data processing success Return example:
## {
"bright": 4356, // The value 0-16384, -1000 indicates that the module is not inserted
"ppm": -1000, //-1000 indicates that the module is not inserted
"temp": 23.6, // Real-time temperature is 23.6, in degrees Celsius
"wet": 64.3, // Real-time humidity is 64.3%
## "code": 200,
"message": "SUCCESS"
## }
5.71 Get the playcard language
## Uri Request
method
## Request
parameters
Return value
getLanguages GET no { code: 200,
data: {
"enName": "zh",
"zhName": "Simplified Chinese"
## },
"message": "SUCCESS"}
// The first in the list of returned languages is the language currently in use
Example send data instruction format:
Http://192.168.0.100:18080/getLanguages

Received data processing successful Return example:

## {
## "code": 200,
## "data": [
## {
"enName": "zh",
"zhName": "Simplified Chinese"
## },
## {
"enName": "en",
"zhName": "English"
## },
## {
"enName": "vi",
"zhName": "Ti Vi t"
## }
## ],
"message": "SUCCESS"
## }

5.72 Set the playcard language
## Uri Request
method
Request parameters Return value
setLanguage POST String language;
// Delivered according
to the obtained
enName
## {code:xxx,message:xxxxx}
// Current supported languages: Simplified Chinese (zh), English (en), Vietnamese (vi)

Example send data instruction format:
Http://192.168.0.100:18080/setLanguage? language=en
// Set the playcard language to English

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.73 Set the input source HDMI resolution
// Set the edid of the player card input source
// Support device: KP1H&KP2H&KP4H
## Uri Request
method
Request parameters Return value
setEdid POST int width;
int height;
## {code:xxx,message:xxx
xx}

Example send data instruction format:
Http://192.168.0.100:18080/setEdid? width=1920&height=1080

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.74 Get the input source HDMI resolution
// Supported device: KP1H&KP2H&KP4H
## Uri Request
method
Request parameters Return value
getEdid GET no {code:xxx,message:xxx
xx,
width:xxx,height:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getEdid

Received data processing success Return example:
## {
## "height": 0, // Height
"startX": 0, // This argument is not used
"startY": 0, // This parameter is not used
"status": 0, // This parameter is not used
"width": 0, // width
## "code": 200,
"message": "SUCCESS"
## }

5.75 Set the Playcard output crop area (partial display)
KP1H&KP2H&KP4H to use
// Crop out the display area of the player card input signal source
// Support device: KP1H&KP2H&KP4H
## Uri Request
method
Request parameters Return value
setInputSourceCrop POST int  status;    //1  takes  effect,  0
does not
int startX;
int startY;
int width;
int height;
int inputSource;
// Signal source:
Asynchronous signal
## TYPE_HDMI: 3
Synchronous signal
## TYPE_ANDROID: 2
## {code:xxx,mes
sage:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/setInputSourceCrop?
status=1&startX=100&startY=100&width=768&height=512&inputSource=3
// Crop out the playcard input signal source area (100,100,768,512) for display.

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

KP1HC&KP2HC&KP4HC used
// Crop out the display area of the playcard input signal source
// Support device: KP1HC&KP2HC&KP4HC
## Uri Request
method
Request parameters Return value
setHdmiCrop POST int  isMirror;    // Whether  the
image    is    mirrored,    0    the
original image is mirrored
int x;
int y;
int width;
int height;
## {code:xxx,mes
sage:xxxxx}



Example send data instruction format:
Http://192.168.0.100:18080/ setHdmiCrop? x=0&y=0&width=768&height=512&isMirror=0
// Crop out the playcard input signal source area (0,0,768,512) for display.

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.76 Gets the playcard output crop area value
// Supported devices: KP2H&KP4H
## Uri Request
method
## Request
parameters
Return value
getInputSourceCrop POST/GET int inputSource;
// Signal source:
Asynchronous signal
## TYPE_HDMI: 3
Synchronous signal
## TYPE_ANDROID: 2
## {code:xxx,message:xxxx,
width:xxx,height:xxx,
startX:XXX,startY:xxx,
status:0/1}

Example send data instruction format:
Http://192.168.0.100:18080/getInputSourceCrop? inputSource=3
// Crop out the playcard output area (100,100,768,512) for display

Received data processing success Return example:
## {
"height": 512, // Crop height
"startX": 100, // Crop the starting value of the horizontal coordinate
"startY": 100, // Crop the ordinate starting value
"status": 1, // The clipping function is enabled, 0 is off, 1 is on
"width": 768, // Crop width
## "code": 200,
"message": "SUCCESS"
## }


5.77 Set  the  playback  card  output  image  scaling  (image
parameters)
// Scale the output image to a certain area size display
// Support device: KP2H&KP4H
## Uri Request
method
Request parameters Return value
setHdmiScale POST int  status;    //1  takes  effect,  0
does not
int startX;
int startY;
int width;
int height;
int inputSource;
// Signal source:
Asynchronous signal
## TYPE_HDMI: 3
Synchronous signal
## TYPE_ANDROID: 2
## {code:xxx,mes
sage:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/ setHdmiScale?
status=1&startX=0&startY=0&width=768&height=512&inputSource=3
// Scale the output image to the (0,0,768,512) area for display
// startX and startY are generally set to 0

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.78 Gets the playback card output image scaling value
// Support device: KP1H&KP2H&KP4H
## Uri Request
method
Request parameters Return value
getHdmiScale POST int inputSource;
// Signal source:
Asynchronous signal
## {code:xxx,message:xxxx,
width:xxx,height:xxx,
startX:XXX,startY:xxx,

## TYPE_HDMI: 3
Synchronous signal
## TYPE_ANDROID: 2
status:0/1}

Example send data instruction format:
Http://192.168.0.100:18080/getHdmiScale? inputSource=3

Received data processing success Return example:
## {
"height": 512, // Scale height
"startX": 0, // is generally 0 and is not modified
"startY": 0, // Generally 0, not modified
"status": 1, // The zoom function is enabled, 0 is off, 1 is on
"width": 768, // Zoom width
## "code": 200,
"message": "SUCCESS"
## }

5.79 Set the playcard to restart at a scheduled time
// If the player card is powered on for 24 hours, it is recommended to enable the timed restart
function
## Uri Request
method
Request parameters Return value
setAutoReboot POST int status //0 off, 1 on
string  rebootTime  //  As  in
## 02:00:00
## {code:xxx,message:x
xxxx}

Example send data instruction format:
Http://192.168.0.100:18080/setAutoReboot? status=1&rebootTime=02:00:00
// Enable a daily restart at 2am
// To disable, set status to 0

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.80 Get the playcard timed restart status
// Support device: KP2H&KP4H
## Uri Request
method
## Request
parameters
Return value
getAutoReboot GET no {code:xxx,message:xxxxx,
int status,
string rebootTime
## }

Example send data instruction format:
Http://192.168.0.100:18080/getAutoReboot

Received data processing successful Return example:
## {
"rebootTime": "02:00:00",
## "status": 1,
## "code": 200,
"message": "SUCCESS"
## }

5.81 Delete unused resources from the playcard
// Free up memory and delete material that is not referenced by the program
## Uri Request
method
Request parameters Return value
deleteUnuseMedia GET no {code:xxx,message:xxx
xx,
deleteNum:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/deleteUnuseMedia

Received data processing successful Return example:
## {
"deleteNum": 0, // Number of deleted resources
## "code": 200,
"message": "SUCCESS"
## }


5.82 factory data reset
// Restore the factory configuration information and clear all program resources
// Resolution and network-related parameters will not be cleared for the player card output
by the network port
## Uri Request
method
Request parameters Return value
recovery
Use   port  number
## 18081
GET no {code:xxx,message:xxx
xx }

Example send data instruction format:
## Http://192.168.0.100:18081/recovery

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.83 Restore the system to factory Settings
// Call the system to restore factory Settings;
// This interface is equivalent to system reinstallation, all data will be lost, please use caution.
## Uri Request
method
Request parameters Return value
recoverySys
Use   port  number
## 18081
GET no {code:xxx,message:xxx
xx }

Example send data instruction format:
Http://192.168.0.100:18081/recoverySys

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.84 Player software version rollback
// Roll back the player software in the player card to the default system version;
// Player software uninstall reinstall the default version in the system.
## Uri Request
method
Request parameters Returned value
downGrade
Use   port  number
## 18081
GET no {code:xxx,message:xxx
xx }

Example send data instruction format:
Http://192.168.0.100:18081/downGrade

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.85 Gets the current signal source mode
// Support device: KP2H&KP4H
## Uri Request
method
## Request
parameters
Returned value
getSignalInput GET no {code:xxx,message:xxx,
input:xxx }
## //input (
## TYPE_AUTO = 1;
## TYPE_ANDROID = 2;
## TYPE_HDMI = 3;)

Send data instruction format example:
Http://192.168.0.100:18080/getSignalInput

Received data processing successful Return example:
## {
## "input": 1,
## "code": 200,
"message": "SUCCESS"
## }


5.86 Get Playcard status (device running status)
// Obtain the detailed running status of the device, which can be used for troubleshooting
// The returned data can be displayed directly
## Uri Request
method
## Request
parameters
Return value
getDeviceInfo GET no {code:xx,message:xxx,data:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getDeviceInfo

Received data processing successful Return example:
## {
## "code": 200,
"data":  "Device  serial  number:  KP4H21061256\n  Cable  network:  10.10.0.137\n  cloud
platform: connected \n\n \n screen status: normal \n timing play: on \n timing instruction: on
\n synchronous play: not on \n sensor control: not on ",
"message": "SUCCESS"
## }

5.87 Enable/disable Cloud platform connection
// The function of connecting to the cloud platform server can be disabled
// The cloud platform is enabled by default. The default address is admin.kystarcloud.com
## Uri Request
method
## Request
parameters
Return value
setKaresOpen POST int status
//1 Open |0 close

## {code:xxx,message:xxx
xx}

Example send data instruction format:
Http://192.168.0.100:18080/setKaresOpen? status=0
// Turn off cloud platform features

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.88 Set the cloud platform address
// Configure the server address to which the playcard is connected
## Uri Request
method
## Request
parameters
Return value
setKaresHost POST String host;
// can be a domain
name  or  IP  plus  a
port
## {code:xxx,message:xxx
xx}

Example send data instruction format:
Http://192.168.0.100:18080/setKaresHost? host=admin.kystarcloud.com:9060

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.89 Get the cloud platform enabled status
// Cloud platform is enabled on the device by default. The default address is
admin.kystarcloud.com
## Uri Request
method
## Request
parameters
Return value
getKaresStatus GET no {code:xxx,message:xxxxx,
status:0|1, //0 Off, 1 on
host:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getKaresStatus

Received data processing successful Return example:
## {
## "host": "admin.kystarcloud.com",
## "status": 1,
## "code": 200,
"message": "SUCCESS"
## }


5.90 Obtain   the   status   of   cloud platform   disconnection
detection
## Uri Request
method
## Request
parameters
Return value
getCloudReboot
## Status
GET no {code:xxx,message:xxxxx,
status:0|1, //0 Off, 1 on
host:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getCloudRebootStatus

Received data processing successful Return example:
## {
"status": 1, // The cloud platform disconnection detection is enabled
## "code": 200,
"message": "SUCCESS"
## }

5.91 Set enable cloud platform disconnection detection
// The player card can enable the cloud platform connection detection. When the
connection continues to be disconnected, the device will automatically restart and
reconnect
## Uri Request
method
## Request
parameters
Return value
setCloudRebootStatus POST int status:0|1
//0 off 1 On
## {code:xxx,message:xxx
xx}

Example send data instruction format:
Http://192.168.0.100:18080/setCloudRebootStatus? status=1

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.92 Obtain the cloud platform disconnection detection time
// When the disconnection detection is enabled on the player card, the disconnection control
logic is entered after a continuous timeout period
// The default is 20 minutes
## Uri Request
method
## Request
parameters
Return value
getCloudMonitorTi
me
GET no {code:xxx,message:xxxxx,
data:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getCloudMonitorTime

Received data processing successful Return example:
## {
## "code": 200,
"data": 20, // 20 minutes
"message": "SUCCESS"
## }
5.93 Set enable cloud platform disconnection detection
// The player card can enable the cloud platform connection detection. When the
connection continues to be disconnected, the device will automatically restart and
reconnect
## Uri Request
method
## Request
parameters
Returned value
setCloudMonitorTime POST int time;
//   The   unit   is
minutes
## {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/setCloudMonitorTime? time=30
// Set the player card unconnected cloud time to 30 minutes

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.94 Set the synchroplay function
// After multiple player cards are opened, multiple display screens can play content
simultaneously. The default is off
// Currently supports device synchronization in LAN or GPS synchronization in WAN
// Only support the simultaneous playback of timed programs, please upload timed
programs
## Uri Request
method
## Request
parameters
Return value
setSyncPlay POST int status
//1 Open |0 close
int type
## //1(network
sync)|2(GPS sync)
## {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/setSyncPlay? status=1&type=2
// Enable Sync play and set it to GPS sync

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.95 Get the simulcast status
## Uri Request
method
## Request
parameters
Return value
isOpenSyncPlay GET no {code:xxx,message:xxxxx,
status:0|1 //1 Open |0 close
type:1(network sync)|2(GPS
sync)}

Example send data instruction format:
Http://192.168.0.100:18080/isOpenSyncPlay

Received data processing successful Return example:
## {
"status": 0, // off
"type": 1, // LAN synchronization

## "code": 200,
"message": "SUCCESS"
## }
5.96 Set  whether  to  display  the  show  name  when  switching
shows
// When switched on, the name of the currently switched program will be displayed in the
upper left corner of the screen when the program is switched
## Uri Request
method
## Request
parameters
Return value
setShowProgramName POST int status;
// 1 yes | 0 no
## {code:xxx,message:xxx
xx}

Example send data instruction format:
Http://192.168.0.100:18080/setShowProgramName? status=1
// Enable display of program name

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.97 Get whether the show name is displayed when switching
shows
// Restore the factory configuration information and clear all program resources
## Uri Request
method
## Request
parameters
Return value
getShowProgramName GET no {code:xxx,message:xxx
xx,
status:0|1}

Example send data instruction format:
Http://192.168.0.100:18080/getShowProgramName

Received data processing successful Return example:
## {

## "status": 1,
## "type": 0,
## "code": 200,
"message": "SUCCESS"
## }


5.98 Get the playcard log
// Get the log information stored by the playcard, 100,000 are supported
Uri Request method Request
parameters
Return value
zlog GET String start; (start
time yyyyMMdd)
String  end;  (end
time yyyyMMdd)
application/octet-
stream

Example send data instruction format:
Http://192.168.0.100:18080/zlog? start=20221017&end=20221017

Receive the log.db file



5.99 Add the playcard lock password
// Add a lock password to the playcard for security
// This locking method locks the communication channel. For example, after mobile phone
1 is unlocked and logged in, mobile phone 2 also needs to log in. Avoid conventional
methods After the device is unlocked, all clients can access the operation
## Uri Request
method
## Request
parameters
Return value
setLoginPassword POST String password
//  An  empty  value
deletes the
password
## {code:xxx,message:xxx
xx}

Example send data instruction format:
Http://192.168.0.100:18080/setLoginPassword? password=964297


Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.100 Get the playcard locked status
## Uri Request
method
## Request
parameters
Return value
isLogin GET no {code:xxx,message:xxxxx,
data:Int}
data:0  has  no  password,  1
has password
Error  responsecode  404  The
device   does   not   support
locking and can be accessed
directly
Error code 401 Device has a
lock and requires login

Example Send data instruction format:
Http://192.168.0.100:18080/isLogin

No password Received data processed successfully Return example:
## {
## "code": 200,
"data": 0, // No password
"message": "Login successful"
## }

Password received Data processing successful Return example:
## {
"code":  401,  //  When  401  is  returned,  the  device  has  a  password  that  needs  to  be
decrypted and logged in
"message": "Not logged in yet"
## }


## 5.101 Lock Playcard
// When the player card has a password and login state, the operator wants to leave the scene,
for security call this interface can immediately lock the device
## Uri Request
method
## Request
parameters
Returned value
logout GET no {code:xxx,message:xxxxx}

Example send data instruction format:
## Http://192.168.0.100:18080/logout

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.102 Unlock the login Playcard
// Login to this player card, this connection channel can communicate normally
## Uri Request
method
## Request
parameters
Return value
login POST String password  {code:xxx,message:xxxxx}

Example send data instruction format:
Http://192.168.0.100:18080/login? password=964297
// After login, you can access other interfaces normally

Receive data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.103 Forgot password
// When the password set by the player card is forgotten, you can call this interface to get a
string for unlocking
// The password must be remembered

## Uri Request
method
## Request
parameters
Returned value
getPasswordToken GET no {code:xxx,message:xxxxx,
data:"adsfsrwerwesdfsdfsdfs
df"}
// Send the string to the staff
to  get  the  unlock  password
to unlock

Example format of send data instruction:
Http://192.168.0.100:18080/getPasswordToken

Received data processing successful Return example:
## {
## "code": 200,
## "data":
"a7WX7tvlxNQuC0Ew2POPM1VK9Y/+C/DRU0gmINiK/2+6SaK9rlzYm8PCR7Rzb2VpZb2pB/T
zSKmYtcjmg4/jM8vkVDe4YXjLC+iiWiQV3YU9+3Dn7u0QZWb
N5tZFjAf4ZDU9yDJDNthy0mu8xn1FCah3WK5vy ER8r/mRuxXCps = ". / / used to unlock the
content
"message": "SUCCESS"
## }

5.104 Get the send card/receive card information
// Through this interface, you can obtain the number and version of the sending card and
receiving card, which can be used for monitoring the screen, so as to preliminarily judge
whether the screen is running normally
## Uri Request
mode
## Request
paramete
rs
Return value
getCardInfo GET no {"code":200,"data":{rxNum:”8”,
"RxCardList"     :     [[{"     version     ":"
## AA103_A01000  2019.01.23  17:00  ID
number: N/A "}], [], [], []],
"TxCard" : {" version ":" ME101_A0200
## 2020.02.21    11    "}},    "message"    :
## "SUCCESS"}

Example send data instruction format:
Http://192.168.0.100:18080/getCardInfo


Received data processing successful Return example:
## {
## "code": 200,
## "data": {
"rxCardList": [
## [
## {
"version":  "SA102_G01000  2020.07.27  21:00  ID  Number  :a0041802-
00200228" // Version number and ID number of the first receiving card
## },
## {
"version":  "SA102_G01000  2020.07.27  21:00  ID  Number  :a0041802-
## 00200238"
## },
## {
"version": "SA102_G01000 2020.07.27 21:00 ID Number :a0041802--
## 0000115"
## }
## ],
## [],
## [],
## []
## ],
"rxNum": 3, // Number of received cards
"txCard": {
"version": "MQ102_A0100 2021.09.23 21:00" // Send the card version number
## }
## },
"message": "SUCCESS"
## }

5.105 File screen adjustment
// Can be used to upload the screen adjustment file to the playback card to complete the LED
screen adjustment
// You need to use the control card software to export the screen adjustment bin file
## Uri Request
method
Request parameters Return value
txcFileScreen POST
file
## {code:xxx,messag
e:xxx }


Example send data instruction format:

Received data processing successful return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.106 Set the player card network port size parameters
//  You  can  set  the  network  port  size  parameters  of  the  player  card  directly  through  this
interface, without using the card tuning software

## Uri Request
method
## Request
parameters
Return value
setTxcPortSize POST json; // Network port
parameters in
descending order
## {code:xxx,message:xxxx
x}
## // Success 200

Example send data instruction format:
// Set the parameters of the player card 1,2 network ports



Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.107 Usb flash drive live Settings
// Directly play the material (including pictures and videos) in the directory of USB flash
drive
// Playback cards with 1080P decoding can only play videos within 1080P, while playback
cards with 4K decoding can play videos within 4K
## Uri Request
method
Request parameters Return value
usbSetting POST int status
//1   is   open   to   read   the   U   disk
material; 0 indicates off.
int scaleType
// Do  not  pass. 1  for  the  material  to
spread  the  window,  0  for keeping
scale
String text
// Do not pass. Text displayed on top
layer of footage
String dirName
//  Do  not  pass. Specify  the  name  of
the   file   directory   to   be   read.   By
## {code:xxx,message:xxx }

default,  the  material  under  the  root
directory is read

Example send data instruction format:
Http://192.168.0.100:18080/usbSetting? status=1&scaleType=1&text= Example Show text &
dirName= Confidential folder
// Enable direct playback of USB flash drive material; Material spread the window to play; In
the top layer of the material floating scroll "example display text"; Specify the material to read
the "secret folder" on the USB flash drive

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.108 Get USB flash drive live Settings
// When the password set by the playback card is forgotten, you can call this interface to get
a string for unlocking
## Uri Request
method
## Request
paramet
ers
Return value
getUsbParams GET no {code:xxx,message:xxx,
status:xxx  //1  to enable  reading
USB   flash   drive   material;   0
indicates off.
scaleType:xxx // can be null. 1 for
the  material  to  spread  out  the
window, 0 for holding scale
text:xxx //  can  be  empty.  Text
displayed on the top layer of the
footage
dirName:xxx   //   can   be   null.
Specify   the   name   of   the   file
directory  to  be  read,  and  read
the   material   under   the   root
directory for empty}

Send data instruction format example:
Http://192.168.0.100:18080/getUsbParams


Received data processing successful Return example:
## {
"dirName": "Confidential folder ",
"scaleType": 1,
## "status": 1,
"text": "Example display text",
## "code": 200,
"message": "SUCCESS"
## }









5.109 Set the NTP server address
// Can be used to customize the network time server. After the change, the player card obtains
the time from this address. Make sure that the time server is running properly
// The playcard will be connected to the Internet time by default. There is no need to configure
the playcard separately when it is connected to the Internet.

## Uri Request
method
Request parameters Return value
setNtpServer
POST String ntpServer;   //NTP
server   address,   which
can be IP
## {code:xxx,messag
e:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/setNtpServer? NtpServer = 10.10.0.103
// Set NTP server address to 10.10... 0.103

Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


5.110 Get the NTP server address
// Get the player card's current time server address
## Uri Request
method
Request parameters Return value
getNtpServer get
no
## {code:xxx,
## "data":"10.10.0.1
## 03",message:xxx}

Example send data instruction format:
Http://192.168.0.100:18080/getNtpServer

Received data processing successful Return example:
## {
## "code": 200,
## "data": "10.10.0.103",
"message": "SUCCESS"
## }

5.111 Install third-party apps
//  Can  be  used  to  install  third-party  apps  in  the  player  card, support  silent  installation,
automatic installation immediately after downloading, automatically start the software after
starting;
// It can also be used for OTA upgrade of customer app. The customer app can download
the new app installation package by itself and call this interface for upgrade.
## Uri Request
method
Request parameters Return value
uploadThirdApk POST
file
## {code:xxx,messag
e:xxx }

Example send data instruction format:

Received data processing successful return example:
## {

## "code": 200,
"message": "SUCCESS"
## }
5.112 Uninstalling third-party apps
// Uninstall the apps installed in the player card and return to the default player interface of
the player card
## Uri Request
method
Request parameters Return value
uninstallThirdApk GET
no
## {code:xxx,messag
e:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/uninstallThirdApk
Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.113 Get the playcard latitude and longitude
// The player card needs to be equipped with a positioning module
## Uri Request
method
Request parameters Return value
getLatiLongi
## GET
no
## {code:xxx,messag
e:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/getLatiLongi
Received data processing successful Return example:
## {
## "code": 200,
"N2811.78523", // longitude
"E11253.14926" // Latitude
"message": "SUCCESS"
## }


5.114 Text-to-speech broadcast
// Upload a piece of text, and the player card can convert the text to voice playback
## Uri Request
method
Request parameters Return value
speakStart
POST String  content;   // text
content
Float  pitch;      //  audio
playback pitch, 0 to 2.0f
Float  speed;    //  audio
playback    speed,    the
value ranges  from  0  to
## 2.0f
String repeat;  //
Number    of    plays,    0
repeat,  other  times  by
value repeat
## {code:xxx,messag
e:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/speakStart? content= Multilingual intelligent speech technology
refers to the comprehensive technology including multilingual speech recognition,
multilingual speech synthesis, and multilingual translation technology. & pitch = 1.0 1.0
f&repeat f&speed = = 0
// Broadcast this text in a loop, as soon as it is sent

Received data processing success return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.115 Stop the voice announcer
// Immediately stop the current text-to-speech playback and use it in conjunction with the
previous interface
## Uri Request
method
Request parameters Return value
speakStop
## GET
no
## {code:xxx,messag
e:xxx }

Example send data instruction format:

Http://192.168.0.100:18080/speakStop
Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.116 Set the player card real-time screen to be pushed to the
server
//  Can  enable  to  push  the  current  real-time  playback  of  the  player  card  to  the  streaming
media server in the form of a stream;
// There needs to be a server to obtain this stream, and the address of each device needs to
be unique;
//  Enabling  stream  pushing  will  consume  certain  performance  of  the  device,  such  as  the
current playback of large materials, may cause a certain degree of delay.
## Uri Request
method
Request parameters Return value
startLive POST String url;  //
Streaming media server
address

## {code:xxx,messag
e:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/starLive? Url = RTMP: / / 10.10.0.103:1935 / live/KPGA19010048
// Push live footage to this address

Received data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.117 Set the player card real-time screen to be pushed to the
client
// Can be enabled to push the current real-time playback of the player card to the client in
the form of a stream;

// Play card as the server
// Enabling the streaming will consume certain performance of the device. For example, the
current playback of large materials may cause a certain degree of stutch.
// Default access address: rtsp://{player card ip}:1234
## Uri Request
mode
Request parameters Return value
startLiveSever GET no

## {code:xxx,messag
e:xxx }

Example send data instruction format:
HTTP: / / Http://192.168.0.100:18080/startLiveServer / / open local push real-time stream

Receive data processing success Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }

5.118 Stop the playcard to push live content
// Stop pushing streams
## Uri Request
method
Request parameter Return value
stopLive GET no {code:xxx,messag
e:xxx }

Example send data instruction format:
Http://192.168.0.100:18080/stopLive
Received data processing successful Return example:
## {
## "code": 200,
"message": "SUCCESS"
## }


## Addendum
- Entry Animation Corresponding table:
## Serial
number
value Name

1 NONE  no
2 RANDOM  Random animation
3 BAI_YE_CHUANG  Shutters
4 CA_CHU  Top covering
5 CA_CHU_DOWN Under cover
6 CA_CHU_LEFT Left overlay
7 CA_CHU_RIGHT Right overlay
8 HE_ZHUANG  Rectangular
convergence
9 HE_ZHUANG_KUOZHAN  Rectangular
diffusion
10 JIE_TI  Ladder
11 LING_XING  Rhomboid
convergence
12 LING_XING_KUO_ZHAN  Diamond
extension
13 LUN_ZI  Wheels
14 PI_LIE  Close left and right
15 PI_LIE_UP_DOWN  Close up and
down
16 PI_LIE_OPEN  Opening and
closing left and
right
17 PI_LIE_UP_DOWN_OPEN  up_down_open
18 QIE_RU  Move up
19 QIE_CHU  Move down
20 QIE_LEFT  Shift left
21 QIE_RIGHT  Right shift
22 QI_PAN  Chessboard
23 SHAN_XIANG_ZHAN_KAI  Fan out
24 XIANG_NEI_RONG_JIE  Indissolving
25 YUAN_XING  Circular
convergence
26 YUAN_XING_KUO_ZHAN Circular extension



</details>
