# Home Assistant Add-on: Alexa RTSP Doorbell

<a href="https://www.buymeacoffee.com/githubfoxy82" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

## About

Set up a Generic RTSP Camera and a binary sensor to get video notifications to Amazon devices that support live view. Eg. Echo Show.

![Supports aarch64 Architecture][aarch64-shield] ![Supports amd64 Architecture][amd64-shield] ![Supports armhf Architecture][armhf-shield] ![Supports armv7 Architecture][armv7-shield] ![Supports i386 Architecture][i386-shield]

[aarch64-shield]: https://img.shields.io/badge/aarch64-yes-green.svg
[amd64-shield]: https://img.shields.io/badge/amd64-yes-green.svg
[armhf-shield]: https://img.shields.io/badge/armhf-yes-green.svg
[armv7-shield]: https://img.shields.io/badge/armv7-yes-green.svg
[i386-shield]: https://img.shields.io/badge/i386-yes-green.svg
[discord]: https://discord.gg/c5DvZ4e

## Before Starting!

Before starting please note this software is early stage beta. Whilst I have got it to display the doorbell correctly it has been intermittent.
I am releasing this now to see if we can find out how intermittent it is and see if we can improve it. 

Seeing your camera in Alexa requires Alexa being able to connect to the WebRTC stream and success for this will be different depending on your network configuration.

## Prerequisites

This addon assumes you have successfully used the Alexa integration: https://www.home-assistant.io/integrations/alexa/ and the requirements listed there are the same for this addon.

## Install

### Install RTSPToWeb

First you need to install the excellent RTSPToWeb add-on. Follow allenporters instructions here: https://community.home-assistant.io/t/add-on-rtsptoweb-and-rtsptowebrtc/387846

The add-on can be found here: https://github.com/allenporter/stream-addons

### Setup an Alexa Skill

#### Create an Amazon Alexa Smart Home Skill

Follow the instructions here to create an Amazon Alexa Smart Home Skill: [https://www.home-assistant.io/integrations/alexa.smart_home/#create-an-amazon-alexa-smart-home-skill]

#### Create an AWS Lambda Function

Follow the instructions here to create a Lambda Function: [https://www.home-assistant.io/integrations/alexa.smart_home/#create-an-aws-lambda-function]

However use the following code for your lambda function: TODO link

Then under environment use the following:

* `HOSTNAME` : set this to https://<externally accessible name>/api/alexa_rtsp_doorbell
* `PASSWORD` : set this to something that isn't easily guessable - note this down you will need it later when you configure this as `api_password` in this addon.

The testing section won't work yet.

#### Configure the Smart Home Service Endpoint

Follow the instructions here: [https://www.home-assistant.io/integrations/alexa.smart_home/#configure-the-smart-home-service-endpoint]

#### Configure Account Linking

We are going to use "Login With Amazon" for account linking (LWA).

Go to [https://developer.amazon.com/], login, and then click "Developer Console"

On the navbar at the top of the screen click "[Login with Amazon|https://developer.amazon.com/loginwithamazon/console/site/lwa/overview.html]"

Click the "Create a New Security Profile" button

* Enter a "Security Profile Name". e.g. AlexaDoorbell
* Enter a description.
* In the privacy url we can use anything for now as we aren't going to publish this skill e.g. "https://example.com"
* Click Save
* Move over the cog on the Profile you just created and select "Web Settings"
* In the page that opens up copy the client ID and Client Secret down.
* Don't shut this page we will come back to it in a moment!

Now we need to get some information from the Smart Home Skill webpage and set it up. In another tab go to [https://developer.amazon.com/alexa/console/ask]

* Select your skill
* Select "Account Linking"
* Tick the option "Do you allow users to create an account or link to an existing account with you?"
* Make sure the options about "your application or website" and "your mobile application" are NOT ticked.
* Under "Web Authorization URI" enter "https://www.amazon.com/ap/oa"
* Under "Access Token URI" enter "https://api.amazon.co.uk/auth/o2/token"
* Under "Your Client ID" enter the client ID we just copied from LWA
* Under "Your Secret" enter the client secret we just copied from LWA
* Under "Your Authentication Scheme" choose "HTTP Basic"
* Click add scope and type in "profile"
* Click Save
* Copy the 3 "Alexa Redirect URLs"

* Go back to the Login with Amazon page - you should still be in the "Web Settings"
* Click "Edit"
* Paste in the 3 URLS we just copied from the other page.
* Click "Save"

*BE CAREFUL HERE* we have just been working with a client ID/Secret but we are finished with them now. However we do need another one to setup the addon. To get the other one....

* Go back to the Alexa Developer console and click "Permissions"
* Tick the "Send Alexa Events" box
* Under Alexa Skill Messaging
* Copy the Alexa Client Id - we will enter this later as the `alexa_client_id`
* Copy the Alexa Client Secret - we will enter this later as the `alexa_client_secret`
* Click on "Smart Home" on the left side and click "Save"


### Install and configure my addon

#### Configure add-on repository:

Configure the add-on repository https://github.com/foxy82/ha-addons in Home Assistant.

#### Install Alexa Generic RTSP Doorbell

Install the "Alexa Generic RTSP Doorbell" from the repository

#### Configure the Alexa Generic RTSP Doorbell

First setup the generic config:

```yaml
oauth_token_url: null
alexa_event_gateway_url: null
alexa_client_id: null
alexa_client_secret: null
rtsp_to_webrtc_url: null
api_password: null
```

* oauth_token_url - Find your nearest from this link: [https://developer.amazon.com/docs/login-with-amazon/authorization-code-grant.html#access-token-request]
* alexa_event_gateway_url - Find your nearest from this link: [https://developer.amazon.com/en-US/docs/alexa/smarthome/send-events-to-the-alexa-event-gateway.html#endpoints]
* alexa_client_id: Found in the Alexa Skill Developer console under permissions - Alexa Skill Messaging.
* alexa_client_secret: Found in the Alexa Skill Developer console under permissions - Alexa Skill Messaging.
rtsp_to_webrtc_url: Go to the RTSPtoWeb addon and on the "Info" tab you will see some text like this: "Hostname `3d360630-rtsp-to-web`", then go to configuration and check which port you used (default is 8083). Enter this as: `http://3d360630-rtsp-to-web:8083`. Alternatively you can run the RTSPToWeb server on another machine and adjust this as you need.
* api_password: This is the password we used later.

Now we need to add our doorbells. You can have more than one but the doorbell / motion sensor needs to be unique for each one Eg.

```yaml
doorbells:
  - alexa_friendly_name: <The name that alexa will announce>
    alexa_endpoint: <A unique name to be used by alexa. Only letters/underscore>
    doorbell_sensor: Optional - <The name of a home assistant entity that turns on and off> when it turns on Alexa will announce "There is someone at the Door" (or similar) and will display the camera. You are responsible for turning this entity back off e.g. with a Home Assistant automation
    motion_sensor: Optional - <The name of a home assistant entity that turns on and off> when it turns on Alexa will announce 
    rtsp_to_webrtc_stream_id: You get this from 
    rtsp_to_webrtc_channel_id: <The channel ID from RTSPToWeb first channel is 0>
  - alexa_friendly_name: Another doorbell
    ... 
```

The steam ID can be found using the RTSPToWebRTC API: [https://github.com/deepch/RTSPtoWeb/blob/master/docs/api.md]

However if you set the doorbell part of the config to an empty list
```yaml
doorbells: []
```
Start the addon and check the logs you will see lines like this:
```
RTSPToWeb STREAM: Fonrt Door - 216e1816-67cd-74aa-16ba-4bb342bd1115
RTSPToWeb STREAM: Back Gate - 116e1816-76bb-47bb-16ba-4bb253db1151
```

Make the changes to add the `doorbells` in and restart the addon.

#### Test the Add on

Make sure the addon is running by checking the logs tab in the supervisor.

Once all of the above is done you need to link the skill. Go into the Alexa app on your phone or the website: [https://alexa.amazon.com/]

* Select "Skills"
* Select "Your Skills"
* Select "Dev Skills"
* You should see the skill we just created - click on it. 
* It should say "account linking is required" - click "enable"
* You will be redirected to login with amazon - the addon or skill can't see your username/password this is kept between you and amazon.
* Click "Allow"

If you now refresh the addon logs you should see some logging showing messages arrived. Check for any `ERROR`

Now you can discover devices - either click the button that appears in the website/app or ask "Alexa discover devices". You should get the newly configured doorbell(s).

Go into the Alexa App on your phone and find the newly added devices. Click on them and click the Gear icon to go into the setup screen.

In here select the Echo devices you want announcements on and also turn on the Doorbell Press Announcement  and Motion Announcement.

Now all of the following should work (although see my note right at the top of this file!)

* You can see a view of the camera in the Alexa App by clicking on it.
* You can say "Alexa show me the <name>" and see the video on an Echo Show
* If you configured a doorbell it will be announced on any devices you selected. If any support live view you should see a view of the camera.
* If you configured a motion sensor it will be announced on any devices you selected. NOTE: It appears that Amazon don't support video for motion sensors.

## Add On Rest API

This addon supports a very simple REST API to allow doorbell/motion to be triggered. This will work if you don't want to use Home Assistant to trigger this for whatever reason. 

These are the supported GET request. You will also need to add a header `x-alexa-api-key`  set to the `api_password`` 
* http://<homeassistant_ip>:<port>/api/alexa_rtsp_doorbell/doorbell/<alexa_endpoint>
* http://<homeassistant_ip>:<port>/api/alexa_rtsp_doorbell/motion/<alexa_endpoint>/detected
* http://<homeassistant_ip>:<port>/api/alexa_rtsp_doorbell/motion/<alexa_endpoint>/not_detected

```
curl -X GET -H 'x-alexa-api-key:my_password' -H "Content-Type: application/jso
n" http://192.168.1.1:5000/api/alexa_rtsp_doorbell/doorbell/front_door
```

NOTE: I've noticed problems when using `$` with curl so might be best to avoid it in your password

## TODO / Your help.

I need a few things from people that use this.

1. If you liked this and it works for you please click the Buy me a coffee button - this took a lot of time to code.
1. Apparently the notification should work on newer Fire TV Sticks - if it does/doesn't can you let me know which models. I know it doesn't work on the older FireTV 4K diamond pendant.
1. I get this only working  intermittently. I'd like to know the experince others get and if you can know a bit about WebRTC any help debugging is appreciated.
1. There is an interesting US specific Alexa capability here: [https://developer.amazon.com/en-US/docs/alexa/device-apis/alexa-eventdetectionsensor.html] this paired with [Frigate NVR|https://frigate.video/] could be really interesting but alas I'm not in the US so can't test this with coffee and willing testers I might be able to implement this.













