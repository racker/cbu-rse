# RSE Developer Guide

[TOC]

Really Simple Events (RSE) is an API specification for sending and receiving simple notifications in the cloud. RSE isn't meant to be a complete ESB *per se*; rather, RSE is designed to complement transactional job queuing services such as Amazon's SQS or RabbitMQ. Due to the TTL constraint on events, RSE is best used for distributing ephemeral notifications and requests.

The primary advantage that RSE has over alternative protocols is it's stateless, atomic nature. RSE's stateless nature allows it to scale horizontally on cloud infrastructure. Long-lived connections are not required; as long as clients phone home within the event TTL window, they will never miss a message.

RSE is designed to:

- Play nice with firewalls
- Work with both native and web clients
- Be reasonably secure
- Scale to millions of events and hundreds of thousands of clients
- Support multiple delivery schemes, including 1:1 and fan out
- Be ridiculously simple to implement

On the other hand, RSE **is not** designed to:

- Handle transactional job queuing (by itself)
- Pass around large (i.e., 4+ MB) payloads

**NOTE:** For sample PostMan scripts that use RSE (with notes in the description on how to use them), please see [this attachment](https://one.rackspace.com/download/attachments/67998179/RsePostmanSamples.json?version=1&modificationDate=1379344623000&api=v2). You will need Google Chrome to run these scripts.

## RSE vs. X

**Q.** Why not just use PubSubHubub?
**A.** PuSH uses Atom, a heavy protocol designed for syndication, not light-weight event passing. Atom is less readable and requires more bandwidth than RSE's JSON-based protocol. More problematic, however, is the reliance on timestamps to determine what messages you've already seen, vs. an **atom**ic counter (ironic, isn't it?). A chatty event server can easily create collisions, and necessitates inefficient paging to avoid missing any events.

**Q.** But PuSH gets us most of the way there, and uses long-polling vs. “lame, repeated polling.”
**A.** Are you sure you want to use long-polling?. Networking hardware, esp. firewalls, are often optimized around the assumption that HTTP requests are going to be short-lived. Long-polling will quickly saturate your NICs and eat kernel memory for breakfast. In our experience scaling the number of concurrent, long-lived connections is much harder and more fragile than scaling regular, short-lived HTTP requests. However, there is nothing in the RSE spec that prevents you from implementing long-polling if you need it. In fact, it makes sense to have a “realtime” mode that your app can switch to for highly latency-sensitive use cases. A hybrid approach such as this offers far better utilization of your hardware.

**Q.** Did you just imply that long-polling can actually be *less* scalable that short-polling?
**A.** Right. More efficient, but less scalable. Ironic, isn't it?

**Q.** OK then, how about RabbitMQ?
**A.** Maybe someday, but they don't have a real HTTP/cloud story right now. Plus, RabbitMQ doesn't scale-out without an external sharding tier which increases complexity, leading to higher ops and maintenance costs. “AMQP brings complexity and a protocol not optimized for high latency and intermittent connectivity” ([Eric Day @ OpenStack](https://lists.launchpad.net/openstack/msg00612.html)).

**Q.** Fair enough. If it's HTTP you're after, why not use Nginx? I hear they have a pretty sweet plugin for this sort of thing.
**A.** Sounds like you are talking about [Basic HTTP Push Relay](http://pushmodule.slact.net/). While promising, Leo made a couple of critical mistakes. First, he decided to use simple timestamps (naughty, naughty!) to determine which messages the client has already seen. This is OK for a chat server, but **really bad** for a high-volume SOA since you could easily get more than one event with the same timestamp. The other issue is that his module doesn't have a good federation story, so it's really hard to scale out.

**Q.** Hmm. XMPP provides HTTP and federation. Why not just use that?
**A.** XMPP can be–and has been–leveraged as an event bus. However, you have to work around the user account/chat-room model, which makes “channel” management and federation tricky. Plus, XMPP comes with a lot of baggage that you don't need, and is non-trivial to implement. Keep in mind that when you are dealing with hundreds of thousands of clients, a lean and simple protocol can save a lot of bandwidth. In general, XMPP is an OK solution for intranets, whereas RSE is designed more for the cloud.

## Prerequisites

This developer guide assumes you have a working knowledge of basic web programming and the HTTP protocol. HTTP libraries and associated documentation are available for virtually all popular programming languages. We assume you have located an appropriate library and have some tools to work with JSON-formatted data, as well as the ability to generate UUIDs (AKA GUIDs).

In addition, you will need a basic understanding of cryptographic hash functions, and have access to a programming library that can perform the same. You will need a way to encode these hashes as Base64 (a common internet format).

## Client Walk-through

Clients wishing to use an RSE service will all go through the same basic steps.

1. Generate a UUID at startup (no need to do this for every request)
2. Connect to an RSE server over HTTPS and send it a request
3. Receive and parse the response from the RSE server
4. Update “last known ID” with the last ID in the returned events, if any (or first ID, depending on the specified sort order). A different ID is tracked for each channel queried to avoid race conditions.
5. Poll for new events at regular intervals

When submitting an event as part of the request, the event must be serialized as a well-formed JSON document, viz. as a JSON **array** or **object** value type (no other value types are supported). Any binary data must be Base64-encoded.

UUID's are merely used to avoid echoing messages back to the same client that sent them. Clients may use any standard UUID algorithm except V1.

If using short-polling when requesting new events, we recommend dynamically throttling the polling interval depending on expected event traffic. For example, you client might normally poll once every 30 seconds. However, whenever it receives an event, it would poll every 5 seconds for the next 2 minutes in order to be more responsive to subsequent events. You might also choose to enable HTTP keep-alive in your fast-poll mode to further reduce latency.

Keep-alive, long-polling, or some other more sophisticated push-based eventing model may or may not work for you, depending on your situation. For example, long-lived HTTP connections sometimes don't not play nice with firewalls and other networking equipment, even though it would appear to be more efficient. Also, your networking hardware and servers will have to handle a much higher number of concurrent connections than with a short polling model, since those connections aren't naturally amortized across polling delays. You will probably run out of kernel memory before you saturate the CPU.

## Server Walk-through

Severs must follow these steps upon receiving a client request:

1. Deny any non-HTTPS requests (HTTPS required)
2. Validate all input
   1. Characters in the channel strings are limited to letters, numbers, forward-slashes, underscores, and hyphens.
   2. Event documents must contain only valid JSON
   3. The user-agent string should contain a valid UUID and be limited in size and valid characters
   4. Query parameter and header values should be in the expected formats and within expected ranges
3. Authenticate the request (implementation-specific)
4. Authorize the request (implementation-specific)
   1. Based on the given credentials, ensure the client is authorized to access the specified channel
   2. Ensure the client is authorized to GET or POST to the given channels (some channels may be read-only)
5. Determine whether the request is JSONP
6. Serve the response
   1. For regular GETs, return all events for the given channel.
      1. If no events are available, and the request is a regular (non-JSONP) request, the server may return an HTTP status of “204 No Content” with an empty HTTP body.
   2. For JSONP “POST” requests, or regular HTTP POSTs:
      1. Assign the event the next value of the event ID counter
      2. Store the event with its associated ID, channel name, and a “created at” time stamp

In addition, servers will need to periodically purge old events. What constitutes “old” is implementation-defined, but should not be less than 2 minutes in order to give clients plenty of time for polling delays. This timeout also ensures that clients asking for “all events” on a given channel do not end up receiving a long list of stale events. (Typically, clients will ask for “all events” when they first start up and/or have yet to acquire a last-known event ID.)

*Tip: Since each event is associated with a copy of the channel name, there is no need to create/delete channels separately; it will naturally occur as events are persisted and later purged.*

The event ID counter must be global, can never reset, and must be atomically incremented. The easiest way to do this is to simply use an RDBMS table for storing events with an auto-incrementing, unique key for the ID. Depending on your needs, this restriction may be relaxed to something “good enough”, such as a timestamp with millisecond precision (which would mostly avoid race conditions caused by event IDs colliding at the same time a client performs a query on those events).

*Tip: Since the event counter never resets, you probably want to use a 64-bit integer type to ensure you have plenty of headroom, especially if you anticipate heavy traffic for extended time periods (months and/or years).*

**WARNING #1:** RSE relies on HTTPS to ensure privacy and data integrity. The server must be configured to deny all non-HTTPS requests.

**WARNING #2:** To help prevent clients from accessing unauthorized channels, and to avoid leaking sensitive information into server logs, etc., channel names should be obfuscated, or even randomly generated. Alternatively–or in addition to–the previous suggestion, you may choose to perform app-layer encryption as a defense-in-depth measure.

**WARNING #3:** The way in which the client obtains a security token is implementation-defined, but tokens should expire regularly, and the server must generate the token using one or more high-strength cryptographic algorithms (e.g., AES, SHA-2, CSPRNG). A 128-bit token is OK, but we recommend 160 bits or more if you want to be on the safe side.

## Common API Elements

RSE piggy-backs on top of HTTP using a ReST-like protocol. Requests and responses make use of standard HTTP headers and response codes.

### Requirements

- All communication with the RSE server uses **HTTPS**
- Events are always serialized as **JSON**
- All text is encoded as **UTF-8**

### Headers

Each request to an RSE web service must include a set of common HTTP headers. These headers encapsulate host, authentication and version information.

| Header          | Description                                                  | Example                                                      |
| --------------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| Accept          | For normal GET requests, should be “application/json”. For JSONP requests, can be “*/*”, “application/json-p” or “text/javascript” | application/json                                             |
| Accept-Encoding | For GET requests, specifies that you want the result to be compressed. Support is implementation-dependent. | `gzip`                                                       |
| Content-Length  | For POST requests, the length in bytes of the JSON document  | `168`                                                        |
| Date            | The current date and time, using the standard RFC 1123 HTTP date format. | `Tue, 15 Nov 1994 08:12:31 GMT`                              |
| Host            | The host name for the RSE service                            | `rse.example.com`                                            |
| User-Agent      | The name and version of the RSE client, as well as a UUID for that client. RSE uses the UUID to avoid echoing a client's own messages back to the same running instance that sent the event in the first place. | `CrunchyBacon/1.2 uuid/1E23484E-1CCA-11E0-89DD-39D7DED72085` |
| X-Auth-Token    | An example authentication header for token-based auth. Note that the actual authentication method and headers used is implementation-dependent | `BE4FEEEC-565F-11E1-AE8E-417362ECD4D0`                       |
| X-RSE-Version   | The RSE version you are coding against. This ensures that as the API changes, RSE servers can detect legacy clients and avoid breaking them. The current API version is 2012-04-16 and looks suspiciously like a date. | `2012-04-16`                                                 |

## Submitting Events

It’s easy to submit an event to an RSE server. Including the common RSE headers, you simply POST an event to a “channel” URL of your choosing. The channel does not have to be created in advance, nor cleaned up at a later date when no longer needed.

### Request URI

POST https://rse.example.com/ **{channel}**

*Or, for JSONP:*

GET https://rse.example.com/ **{channel}**?method=POST&post-data=**{post-data}**&callback=**{callback}**&sort=**{sort}**

| Parameter | Required?                      | Description                                                  |
| --------- | ------------------------------ | ------------------------------------------------------------ |
| channel   | Yes                            | The scope to associate with this event. Used to route events to only those clients authorized to see them. Also facilitates 1:1, 1:many, and [many:many](http://manymany/) routing schemes. For example, a scope named “global” could be used for software update announcements (1:many), while sending file change notifications to multiple file sync applications ([many:many](http://manymany/)) would want to use a channel name that scoped events per user account. |
| method    | No                             | The HTTP method to use. Set to “POST” to simulate an HTTP POST for JSONP. |
| post-data | Yes, but only when method=POST | Url-encoded JSON document normally included in the body of a real HTTP POST. |
| callback  | Yes, but only for JSONP        | Set to the name of a JavaScript function that will receive the result when using JSONP. |
| sort      | No                             | Set to 1 (default) to sort the results in ascending, chronological order, by ID. Set to -1 to sort in descending order. |

Channel names may only contain letters, numbers, forward-slashes, underscores, and hyphens.

Please note: The server may choose to deny POST requests for some clients (based on RSE-Token). For example, only a software vendor's release management team should be allowed to post software update notifications!

### POST Data

POST data is an event object (of no particular schema) serialized to JSON. The RSE server should validate the JSON document before storing it. The root-level JSON value type must be either a single array or a single object. Even if an event conceptually consists of just a single number or string, it must be encapsulated in one of the aforementioned containers.

### Parsing the Response

RSE responds to successful POSTs with HTTP 201 Created (with an empty body). For JSONP “post” requests, your callback will receive the following “empty body” JSON result:

```
{}
```

## Retrieving Events

When requesting events, clients simply poll an RSE server with a given scope and channel name. As with all RSE requests, clients must include the common RSE headers in each HTTP request.

RSE determines which messages to return in a manner similar to an RSS or Atom feed. In other words, the client either requests all available events, or requests only those events it hasn't seen yet. However, RSE differs in two important respects to RSS and Atom:

1. Rather than using timestamps to differentiate individual documents, RSE uses an monotonic (ever increasing) 64-bit integer (starting at 1). This ensures that two or more events that arrive in the same second (or even millisecond) can still be retrieved by the client without missing the later event.
2. Events expire quickly (implementation dependent, but generally between 2-5 minutes), and are then deleted from the server. Your clients must poll at least at least as often as events expire so that no messages are missed.

### Request URI

GET https://rse.example.com/ **{channel}**?last-known-id=**{last-known-id}**&max-events=**{max-events}**&echo=**{true|false}**&callback=**{callback}**

| Parameter     | Required?                     | Description                                                  |
| ------------- | ----------------------------- | ------------------------------------------------------------ |
| channel       | Yes                           | The channel and scope for this request. Used to route events to only those clients authorized to see them. Also facilitates 1:1, 1:many, and [many:many](http://manymany/) routing schemes. For example, a scope named “global” could be used for software update announcements (1:many), while sending file change notifications to multiple file sync applications ([many:many](http://manymany/)) should use a channel that scopes events per user account. |
| last-known-id | No                            | The last event ID the client received. The server will only return events with higher IDs than the one given. If not specified, all unexpired events are returned. |
| max-events    | No                            | The maximum number of events the server should return to the client. If not specified, the server should use a reasonable default, such as 50. |
| echo          | No                            | Set to “true” if you want the client to receive a copy of any events that it has submitted itself. Defaults to “false”. |
| callback      | Yes, but only for JSONP       | Set to the name of a JavaScript function that will receive the result when using JSONP. |
| sort          | No, defaults to 1 (ascending) | By default, events are sorted in the response by event ID in ascending order (oldest event first). To reverse this order, sort=-1 |

### Parsing the Response

RSE responds to GET requests with a **Container** object (mostly to avoid [this nasty piece of work](http://directwebremoting.org/blog/joe/2007/03/05/json_is_not_as_safe_as_people_think_it_is.html)), containing a copy of the channel requested, as well as an array of events. All text is encoded in UTF-8.

**Container JSON**

| Data Member | Description                                                  | Example                                                      |
| ----------- | ------------------------------------------------------------ | ------------------------------------------------------------ |
| channel     | Name of the channel requested                                | `/8257A100-1CE0-11E0-82B2-A2EEDED72085/commands`             |
| events      | An array of **Event** objects. May be empty if the RSE server could not find any unexpired events for the specified scope and channel. | `[{“id”:274,”user_agent”:“Example uuid/550e8400-dead-beef-dead-446655440000”,”created_at”:“2011-01-12”,”data”:{ “type”:“HelloWorld” }]` |

**Event JSON**

| Data Member | Description                                                  | Example                                                 |
| ----------- | ------------------------------------------------------------ | ------------------------------------------------------- |
| id          | The event ID. A 64-bit, always-increasing integer (starting at 1) that the client can use in subsequent requests as the **last-known-id** parameter. | `274`                                                   |
| user_agent  | The user agent string for the client that originally submitted the event. | `Example/1.2 uuid/550e8400-dead-beef-dead-446655440000` |
| created_at  | Timestamp for when the event was originally submitted (do not use for ordering events unless it's OK for occasional collisions) | `2009-03-16 13:25:29Z`                                  |
| age         | Number of seconds elapsed since created_at, relative to the server's clock |                                                         |
| data        | The event document from the original POST data               | `{ “type”:“FileChanged”, “path”:”/sync/dir” }`          |

## Integrating RSE with Cloud Backup

This is what RSE event containers look like.

1. Note that “data” can be anything as far as RSE is concerned, but we expect a nested rax::Dispatch event in our implementation
2. The “request_id” parameter can be used to tie a response event back to the original request event.
3. MachineAgentId is present for any message destined for a specific agent.
4. Age is the number of seconds since the event was posted

Example event container JSON:

```json
{
    "id"
      :
      12345
      ,
    "user_agent"
      :
      "foo uuid/123abc"
      ,
    "created_at"
      :
      "2009-03-16 13:25:29"
      ,
    "age"
      : 72
      ,
    "data"
      : { 
      "Event"
      :
      "Test"
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "MachineAgentId"
      : 12345
      ,
      "Data"
      : {
        "Whatever"
      : 123
      ,
        "MoreWhatever"
      : [
      ]
      }
    }
  }
```

Example of sending an event data object using the POST method:

```json
{ 
  "Event"
      :
      "Test"
      ,
  "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
  "Data"
      : {
    "Whatever"
      : 123
  }
}
```

## Cloud Backup Events and Data Contracts

Terms:

- Command Events - these are events that are raised by a subscriber for an agent to listen to (typically from a user interaction)
- Raised Events - these are events that are raised to notify any subscribers about an event.

### Command Event: ActivateAccount

 

| **Verb** | **Event**       | **Description**                                              |
| -------- | --------------- | ------------------------------------------------------------ |
| POST     | ActivateAccount | Awaken the Agent from slow poll to high frequency polling of events |

 

“mode” can be one of:

- Idle
- Active
- RealTime

```
  {
    "Event"
      :
      "ActivateAccount"
      ,
    "Data"
      : {
      "Mode"
      : "RealTime"
    }
  }
    
```

### Raised Event: AgentRegistered

 

| **Verb** | **Event**       | **Description**                                   |
| -------- | --------------- | ------------------------------------------------- |
| GET      | AgentRegistered | Raised by the API when a new agent is registered. |

 

The MachineAgentId is REQUIRED in the RSE Message container.

```
  {
      "Event"
      :
      "AgentRegistered"
      ,
      "Data"
      : { 
          "MachineName"
      :
      "My Agent Name"
      ,
          "OperatingSystem"
      :
      "Windows 7"
      ,
          "OperatingSystemVersion"
      :
      "6.1"
      ,
          "Architecture"
      :
      "64-bit"
      ,
          "Status"
      :
      "Online"
      }
  }
    
```

### Raised Event: Heartbeat

 

| **Verb** | **Event** | **Description**                                              |
| -------- | --------- | ------------------------------------------------------------ |
| GET      | Heartbeat | Inform that the agent is currently active. Submitted by the agent |

 

```
  {
      "Event"
      :
      "Heartbeat"
      ,
      "MachineAgentId" : 100213
      ,
      "Data"
      : { }
  }
    
```

### Raised Event: ConfigurationChanged

 

| **Verb** | **Event**            | **Description**                                              |
| -------- | -------------------- | ------------------------------------------------------------ |
| POST     | ConfigurationChanged | Notify the agent that the configuration has changed so that it can download the updated configuration |

 

```
  {
      "Event"
      :
      "ConfigurationChanged"
      ,
      "Data"
      : {
      }
  }
    
```

### Command Event: EnableVolumeEncryption

 

| **Verb** | **Event**              | **Description**                                              |
| -------- | ---------------------- | ------------------------------------------------------------ |
| POST     | EnableVolumeEncryption | Ask the agent to enable volume encryption using the given password. Fails if encryption is already enabled. |

 

```
  {
      "Event"
      :
      "EnableVolumeEncryption"
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Data"
      : {
        "EncryptedPasswordHex"
      : "73553118"
      ,
        "VolumeUri"
      : "rax://storage101.dfw1.clouddrive.com/v1/MossoCloudFS_c2b546a4-23b6-4562-ab1b-584e64cb028e/CloudBackup_v2_0_af8d111d-8ae4-4f42-a759-0f9ed6317e51"
      }
  }
    
```

### Raised Event: VolumeEncryptionEnabled

 

| **Verb** | **Event**               | **Description**                                         |
| -------- | ----------------------- | ------------------------------------------------------- |
| POST     | VolumeEncryptionEnabled | Returns a response to the EnableVolumeEncryption event. |

 

If volume encryption is now enabled, “Succeeded” will be true. Otherwise, “Succeeded” will be false.

```
  {
      "Event"
      :
      "VolumeEncryptionEnabled "
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Succeeded"
      : false
      ,
      "Data"
      : { }
  }
    
```

### Command Event: ChangeVolumePassword

 

| **Verb** | **Event**            | **Description**                             |
| -------- | -------------------- | ------------------------------------------- |
| POST     | ChangeVolumePassword | Ask the agent to change the volume password |

 

```
  {
      "Event"
      :
      "ChangeVolumePassword"
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Data"
      : {
        "OldEncryptedPasswordHex"
      : "deadbeef"
      ,
        "NewEncryptedPasswordHex"
      : "73553118"
      ,
        "VolumeUri"
      : "rax://storage101.dfw1.clouddrive.com/v1/MossoCloudFS_c2b546a4-23b6-4562-ab1b-584e64cb028e/CloudBackup_v2_0_af8d111d-8ae4-4f42-a759-0f9ed6317e51"
      }
  }
    
```

### Raised Event: VolumePasswordChanged

 

| **Verb** | **Event**             | **Description**                            |
| -------- | --------------------- | ------------------------------------------ |
| POST     | VolumePasswordChanged | Response to a ChangeVolumePassword command |

 

If the password was changed, “Succeeded” will be true. Otherwise, “Succeeded” will be false. No reason is given on a failure in order to avoid giving anything away to an attacker.

```
  {
      "Event"
      :
      "VolumePasswordChanged"
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Succeeded"
      : false
      ,
      "Data"
      : { }
  }
    
```

### Command Event: VerifyVolumePassword

 

| **Verb** | **Event**            | **Description**                                              |
| -------- | -------------------- | ------------------------------------------------------------ |
| POST     | VerifyVolumePassword | Ask the agent to verify whether a volume password is correct. |

 

```
  {
      "Event"
      :
      "VerifyVolumePassword"
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Data"
      : {
        "EncryptedPasswordHex"
      : "deadbeef"
      ,
        "VolumeUri"
      : "rax://storage101.dfw1.clouddrive.com/v1/MossoCloudFS_c2b546a4-23b6-4562-ab1b-584e64cb028e/CloudBackup_v2_0_af8d111d-8ae4-4f42-a759-0f9ed6317e51"
      }
  }
    
```

### Raised Event: VolumePasswordVerified

 

| **Verb** | **Event**              | **Description**                            |
| -------- | ---------------------- | ------------------------------------------ |
| GET      | VolumePasswordVerified | Response to a VerifyVolumePassword command |

 

```
  {
      "Event"
      :
      "VolumePasswordVerified"
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Data"
      : {
        "PasswordIsValid"
      : true
      }
  }
    
```

### Raised Event: Shutdown

 

| **Verb** | **Event** | **Description**                   |
| -------- | --------- | --------------------------------- |
| ?        | Shutdown  | Notify the agent is shutting down |

 

```
{
 "Event": "Shutdown",
 "RequestId": "c50999c1-3405-4bce-84af-fd91182cdef5",
 "Succeeded": true,
 "Data" : { },
 "MachineAgentId": 123456
}
```

### Raised Event: VaultDbDownloadInProgress

 

| **Verb** | **Event**                 | **Description**                                              |
| -------- | ------------------------- | ------------------------------------------------------------ |
| POST     | VaultDbDownloadInProgress | Notify that the vault database is currently being downloaded. Submitted by the agent |

 

```
  {
      "Event"
      :
      "VaultDbDownloadInProgress"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f" // the requestid of the command that initiated this.
      "Data"
      : {
      }
  }
    
```

### Raised Event: VaultDbDownloadCompleted

 

| **Verb** | **Event**                | **Description**                                              |
| -------- | ------------------------ | ------------------------------------------------------------ |
| POST     | VaultDbDownloadCompleted | Notify that the vault database download is complete. Submitted by the agent |

 

```
  {
      "Event"
      :
      "VaultDbDownloadCompleted"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Data"
      : {
      }
  }
    
```

### Raised Event: VaultDbDownloadFailed

 

| **Verb** | **Event**             | **Description**                                    |
| -------- | --------------------- | -------------------------------------------------- |
| POST     | VaultDbDownloadFailed | Notify that the vault database download has failed |

 

```
  {
      "Event"
      :
      "VaultDbDownloadFailed"
      ,
      "RequestId"
      : "19bb384f-7936-48cd-b11e-cc0eb3bde85f"
      ,
      "Data"
      : {
      }
  }
    
```

### Command Event: StartCleanup

 

| **Verb** | **Event**    | **Description**                                           |
| -------- | ------------ | --------------------------------------------------------- |
| POST     | StartCleanup | Notify the agent that it should start the cleanup process |

 

```
  {
      "Event"
      :
      "StartCleanup"
      ,
      "Data"
      : {
        "CleanupId"
      : 2
      ,
        "VolumeSource"
      : {  // the details for the volume source of this vault to clean
             "DataServicesDomain"
      : "Not Implemented"
      ,
             "Uri"
      : "rax://storage101.dfw1.clouddrive.com/v1/MossoCloudFS_c2b546a4-23b6-4562-ab1b-584e64cb028e/CloudBackup_v2_0_af8d111d-8ae4-4f42-a759-0f9ed6317e51"
      ,
             "EncryptionEnabled"
      : false
      ,
             "Password"
      : ""
      ,
             "NetworkDrives"
      : ""
      ,
             "BackupVaultId"
      : "af8d111d-8ae4-4f42-a759-0f9ed6317e51"
         }
      }
  }
    
```

### Command Event: StopCleanup

 

| **Verb** | **Event**   | **Description**                                        |
| -------- | ----------- | ------------------------------------------------------ |
| POST     | StopCleanup | Notify the agent to stop the currently running cleanup |

 

```
  {
      "Event"
      :
      "StopCleanup"
      ,
      "Data"
      : {
        "CleanupId"
      : 2,
      }
  }
    
```

### Raised Event: CleanupProgress

 

| **Verb** | **Event**       | **Description**                                              |
| -------- | --------------- | ------------------------------------------------------------ |
| GET      | CleanupProgress | Inform the subscribers of the current cleanup progress. Submitted by the agent |

 

```
  {
      "Event"
      :
      "CleanupProgress"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "CleanupId" : 1
      ,
        "BytesCompleted" : 1024
      ,
        "BytesRemaining" : 9934
      ,
        "BytesTotal" : 10958
      }
  }
    
```

### Raised Event: CleanupQueued

 

| **Verb** | **Event**     | **Description**                                              |
| -------- | ------------- | ------------------------------------------------------------ |
| POST     | CleanupQueued | Notify that the cleanup has been queued. Submitted by the agent |

 

```
  {
      "Event"
      :
      "CleanupQueued "
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "CleanupId" : 2
      }
  }
    
```

### Raised Event: CleanupInProgress

 

| **Verb** | **Event**         | **Description**                                              |
| -------- | ----------------- | ------------------------------------------------------------ |
| POST     | CleanupInProgress | Notify that the cleanup is in progress. Submitted by the agent |

 

```
  {
      "Event"
      :
      "CleanupInProgress "
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "CleanupId" : 2
      }
  }
    
```

### Raised Event: CleanupCompleted

 

| **Verb** | **Event**        | **Description**                                              |
| -------- | ---------------- | ------------------------------------------------------------ |
| POST     | CleanupCompleted | Notify that the cleanup has completed. Submitted by the agent |

 

```
  {
      "Event"
      :
      "CleanupCompleted"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "CleanupId" : 2
      }
  }
    
```

### Raised Event: CleanupFailed

 

| **Verb** | **Event**     | **Description**                    |
| -------- | ------------- | ---------------------------------- |
| POST     | CleanupFailed | Notify that the cleanup has failed |

 

```
  {
      "Event"
      :
      "CleanupFailed"
      ,
      "Data"
      : {
        "CleanupId" : 2
      }
  }
    
```

### Raised Event: CleanupStopped

 

| **Verb** | **Event**      | **Description**                            |
| -------- | -------------- | ------------------------------------------ |
| POST     | CleanupStopped | Notify that the cleanup has been cancelled |

 

```
  {
      "Event"
      :
      "CleanupStopped"
      ,
      "Data"
      : {
        "CleanupId" : 2
      }
  }
    
```

### Command Event: StartBackup

 

| **Verb** | **Event**   | **Description**                                              |
| -------- | ----------- | ------------------------------------------------------------ |
| POST     | StartBackup | Notify the agent to start the backup with the given BackupConfigurationId. BackupId represents the instance that is running and should be used by the agent for reporting. |

 

```
  {
      "Event"
      :
      "StartBackup"
      ,
      "Data"
      : {
        "BackupConfigurationId" : 1
      ,
        "BackupId" : 1
      }
  }
    
```

### Command Event: StartBackupPreview

 

| **Verb** | **Event**          | **Description**                                              |
| -------- | ------------------ | ------------------------------------------------------------ |
| POST     | StartBackupPreview | Notify the agent to start a backup preview with the given BackupConfigurationId. BackupPreviewId represents the instance that is running and should be used by the agent for reporting. |

 

```
  {
      "Event"
      :
      "StartBackupPreview"
      ,
      "Data"
      : {
        "BackupConfigurationId" : 1
      ,
        "BackupPreviewId" : 1
      }
  }
    
```

### Command Event: StopBackup

 

| **Verb** | **Event**  | **Description**                                              |
| -------- | ---------- | ------------------------------------------------------------ |
| POST     | StopBackup | Notify the agent to stop the currently running backup with the given backup id |

 

```
  {
      "Event"
      :
      "StopBackup"
      ,
      "Data"
      : {
        "BackupConfigurationId" : 1
      ,
        "BackupId" : 1
      }
  }
    
```

### Raised Event: BackupProgress

 

| **Verb** | **Event**      | **Description**                                              |
| -------- | -------------- | ------------------------------------------------------------ |
| GET      | BackupProgress | Inform the subscribers of the current backup progress. Submitted by the agent |

 

```
  {
      "Event"
      :
      "BackupProgress"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "BackupId" : 1
      ,
        "BackupConfigurationId" : 2
      ,
        "BytesCompleted" : 1024
      ,
        "BytesRemaining" : 9934
      ,
        "BytesTotal" : 10958
      }
  }
    
```

### Raised Event: BackupQueued

 

| **Verb** | **Event**    | **Description**                                              |
| -------- | ------------ | ------------------------------------------------------------ |
| GET      | BackupQueued | Inform subscribers that the backup has been queued and is awaiting execution. Submitted by the agent |

 

```
  {
      "Event"
      :
      "BackupQueued"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "BackupId" : 1
      ,
        "BackupConfigurationId" : 2
      }
  }
    
```

### Raised Event: BackupPreparing

 

| **Verb** | **Event**       | **Description**                                              |
| -------- | --------------- | ------------------------------------------------------------ |
| GET      | BackupPreparing | Inform subscribers that the backup is preparing to execute. Submitted by the agent |

 

```
  {
      "Event"
      :
      "BackupPreparing"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "BackupId" : 1
      ,
        "BackupConfigurationId" : 2
      ,
      }
  }
    
```

### Raised Event: BackupInProgress

 

| **Verb** | **Event**        | **Description**                                              |
| -------- | ---------------- | ------------------------------------------------------------ |
| GET      | BackupInProgress | Inform subscribers that the backup is in progress. Submitted by the agent |

 

```
  {
      "Event"
      :
      "BackupInProgress"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "BackupId" : 1
      ,
        "BackupConfigurationId" : 2
      }
  }
    
```

### Raised Event: BackupCompleted

 

| **Verb** | **Event**       | **Description**                                              |
| -------- | --------------- | ------------------------------------------------------------ |
| GET      | BackupCompleted | Inform subscribers that the backup has completed. Submitted by the agent |

 

```
  {
      "Event"
      :
      "BackupCompleted"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "BackupId" : 1
      ,
        "BackupConfigurationId" : 2
      }
  }
    
```

### Raised Event: BackupFailed

 

| **Verb** | **Event**    | **Description**                                 |
| -------- | ------------ | ----------------------------------------------- |
| GET      | BackupFailed | Inform the subscribers that a backup has failed |

 

```
  {
      "Event"
      :
      "BackupFailed"
      ,
      "Data"
      : {
        "BackupId"
      : 1
      ,
        "BackupConfigurationId" : 2
      ,
        "FailedTime" : "2011-04-08 13:25:29"
      }
  }
    
```

### Raised Event: BackupMissed

 

| **Verb** | **Event**       | **Description**                                    |
| -------- | --------------- | -------------------------------------------------- |
| GET      | BackupCompleted | Inform subscribers that the backup has been missed |

 

```
  {
      "Event"
      :
      "BackupMissed"
      ,
      "Data"
      : {
        "BackupId" : 1
      ,
        "MissedTime" : "2011-04-08 13:25:29"
      }
  }
    
```

### Raised Event: BackupSkipped

 

| **Verb** | **Event**       | **Description**                                     |
| -------- | --------------- | --------------------------------------------------- |
| GET      | BackupCompleted | Inform subscribers that the backup has been skipped |

 

```
  {
      "Event"
      :
      "BackupSkipped"
      ,
      "Data"
      : {
        "BackupId" : 1
      ,
        "BackupConfigurationId" : 2
      ,
        "SkippedTime" : "2011-04-08 13:25:29"
      }
  }
    
```

### Raised Event: BackupStopped

 

| **Verb** | **Event**     | **Description**                                  |
| -------- | ------------- | ------------------------------------------------ |
| GET      | BackupStopped | Inform the subscribers that a backup has stopped |

 

```
  {
      "Event"
      :
      "BackupStopped"
      ,
      "Data"
      : {
        "BackupId"
      : 1
      ,
        "BackupConfigurationId" : 2
      ,
        "StoppedTime" : "2011-04-08 13:25:29"
      }
  }
    
```

### Notify Event: BrowseBackup

 

| **Verb** | **Event**    | **Description**                                          |
| -------- | ------------ | -------------------------------------------------------- |
| POST     | BrowseBackup | Notify the agent to browse the given backup vault folder |

 

PatternEncoded is an optional field. It is the Base64 Encoded folder path and appears if the folder path includes a non-UTF8 character. If this field is used the folder to browse will be appended after a folder separator. It is possible both the base folder, and the folder to browse could both be base64 encoded, in that case they are still separated by a folder separator. (Eg. “friFIJIJFRjfjf\\myfolder\\” or “jfkdjfdjk\\fjdkjfdj”.)

```
  {
      "Event"
      :
      "BrowseBackup"
      ,
      "RequestId" : "<guid>"
      "Data"
      : {
        "BackupConfigurationId" : 1
      ,
        "SnapshotId" : 2
      ,
        "Pattern" : "<path>"
      ,
        "PatternEncoded" : "dGhpc2lzbXlmaWxlLmpwZw==\\folderToBrowse\\"
      ,
        "VolumeSource"
      : {  // the details for the volume source of this backup snapshot
             "DataServicesDomain"
      : "Not Implemented"
      ,
             "Uri"
      : "rax://storage101.dfw1.clouddrive.com/v1/MossoCloudFS_c2b546a4-23b6-4562-ab1b-584e64cb028e/CloudBackup_v2_0_af8d111d-8ae4-4f42-a759-0f9ed6317e51"
      ,
             "EncryptionEnabled"
      : false
      ,
             "Password"
      : ""
      ,
             "NetworkDrives"
      : ""
      ,
             "BackupVaultId"
      : "af8d111d-8ae4-4f42-a759-0f9ed6317e51"
         }
      }
  }
    
```

### Raised Event: BackupBrowsed

 

| **Verb** | **Event**     | **Description**                                              |
| -------- | ------------- | ------------------------------------------------------------ |
| GET      | BackupBrowsed | Inform subscribers that a backup has been browsed (using the requestid of the original request being responded to) |

 

If the path(s) matching “Pattern” were not found, “Succeeded” will be set to false and “Items” will be empty.

FolderEncoded is an optional field. It is the Base64 Encoded folder path and appears if the folder path includes a non-UTF8 character.

NameEncoded is an optional field. It is the Base64 Encoded file name and appears if the file name includes a non-UTF8 character.

```
  {
      "Event"
      :
      "BackupBrowsed"
      ,
      "RequestId"
      : "<guid>"
      ,
      "Succeeded"
      : true
      "Data"
      : {
          "Folder"
      : "c:\\some\\folder\\with\\trailing\\path\\separator\\"
      ,
          "FolderEncoded"
      : "YzpcXHNvbWVcXGZvbGRlclxcd2l0aFxcdHJhaWxpbmdcXHBhdGhcXHNlcGFyYXRvclxc"
      ,
          "Items"
      : [
              {
                  "Name" : "<file/folder name>"
      ,
                  "NameEncoded" : "dGhpc2lzbXlmaWxlLmpwZw=="
      ,
                  "Size" : <size of folder/file>,
                  "MimeType" : "<application/pdf>, <application/folder>, <etc>"
              }
      ,
              {
                  "Name" : "<file/folder name>"
      ,
                  "Size" : <size of folder/file>,
                  "MimeType" : "<application/pdf>, <application/folder>, <etc>"
              }
          ]
      }
  }
    
```

### Notify Event: BrowseFolder

 

| **Verb** | **Event**    | **Description**                                    |
| -------- | ------------ | -------------------------------------------------- |
| POST     | BrowseFolder | Notify the agent to browse the given system folder |

 

PatternEncoded is an optional field. It is the Base64 Encoded folder path (“pattern”) and appears if the folder path includes a non-UTF8 character.

```
  {
      "Event"
      :
      "BrowseFolder"
      ,
      "RequestId" : <guid>
      "Data"
      : {
        "Pattern" : "<path>"
      ,
        "PatternEncoded" : "dGhpc2lzbXlmaWxlLmpwZw=="
      ,
      }
  }
    
```

### Raised Event: FolderBrowsed

 

| **Verb** | **Event**     | **Description**                                              |
| -------- | ------------- | ------------------------------------------------------------ |
| GET      | FolderBrowsed | Inform subscribers that a folder has been browsed (using the requestid of the original request being responded to) |

 

In the interest of keeping the event data size to a minimum (to decrease transmission time and allow for folders containing thousands of files even with long path names), only filenames are returned. To construct a full path, simply concatenate the value of “Folder” with File.Name.

If the path given by “Folder” was not found or the agent doesn't have permission to access it, “Succeeded” will be set to false and “Items” will be empty.

Note: It's important that the agent provide a trailing path separator character to the “Folder” path, since the API can not be expected to know the proper character to use when concatenating.

FolderEncoded is optional field. It is the Base64 Encoded folder path and appears if the folder path includes a non-UTF8 character.

NameEncoded is optional field. It is the Base64 Encoded file name and appears if the file name includes a non-UTF8 character.

Mime/Content Types as defined by : http://www.iana.org/assignments/media-types/index.html

```
  {
      "Event"
      :
      "FolderBrowsed"
      ,
      "RequestId"
      : "<guid>"
      ,
      "Succeeded"
      : true
      "Data"
      : {
          "Folder"
      : "c:\\some\\folder\\with\\trailing\\path\\separator\\"
      ,
          "FolderEncoded"
      : "YzpcXHNvbWVcXGZvbGRlclxcd2l0aFxcdHJhaWxpbmdcXHBhdGhcXHNlcGFyYXRvclxc"
      ,
          "Items"
      : [        
              {
                  "Name" : "<file/folder name>"
      ,
		  "NameEncoded"
      : "YzpcXHNvbWVcXGZvbGRlclxcd2l0aFxcdHJhaWxpbmdcXHBhdGhcXHNlcGFyYXRvclxc"
      ,
                  "Size" : <size of folder/file>,
                  "MimeType" : "<application/pdf>, <application/folder>, <etc>"
              }
      ,
              {
                  "Name" : "<file/folder name>"
      ,
                  "Size" : <size of folder/file>,
                  "MimeType" : "<application/pdf>, <application/folder>, <etc>"
              }
          ]
      }
  }
    
```

### Command Event: StartRestore

**Proposed Change**

**TODO:** Add Volume config if a volume/vault that the agent doesn't own (also need to do this for BrowseBackup)

 

| **Verb** | **Event**    | **Description**                     |
| -------- | ------------ | ----------------------------------- |
| POST     | StartRestore | Notify the agent to start a restore |

 

PatternEncoded is optional field. It is the Base64 Encoded file path and appears if the file path includes a non-UTF8 character.

```
  {
      "Event"
      :
      "StartRestore"
      ,
      "Data"
      : {
        "RestoreId" : 1
      ,
        "RestoreBackupConfigurationId"
      : 123
      , // this is the backup configuration this snapshot belongs to
        "RestoreFromSnapshotId"
      : 254
      ,  //this is the snapshot version to restore from (if emptyString, restore from latest snapshot)
        "OverwriteFiles" : true // overwrite existing files if true
        "Inclusions" : [ // the array of files/folders to restore (including subfolders/files) (if blank, restore all)
            {
            "Id" : 123
      , // vault file/folder id not currently implemented
            "Pattern" : "<file path>"
      ,
            "PatternEncoded"
      : "YzpcXHNvbWVcXGZvbGRlclxcd2l0aFxcdHJhaWxpbmdcXHBhdGhcXHNlcGFyYXRvclxc"
      ,
            "Type" : "File|Folder|Wildcard" // wildcard not currently implemented
            }
         ]
      , 
        "Exclusions" : [ // the array of files/folders to exclude from the restore (including its subfolders/files) (if blank, exclude none)
            {
            "Id" : 123
      , // vault file/folder id not currently implemented
            "Pattern" : "<file path>"
      ,
            "Type" : "File|Folder|Wildcard" // wildcard not currently implemented
            }
         ]
      , 
        "Destination"
      : "<Destination Path>" //(if blank, restore to its original file location)
        "VolumeSource"
      : {  // the details for the volume source of this backup snapshot
             "DataServicesDomain"
      : "Not Implemented"
      ,
             "Uri"
      : "rax://storage101.dfw1.clouddrive.com/v1/MossoCloudFS_c2b546a4-23b6-4562-ab1b-584e64cb028e/CloudBackup_v2_0_af8d111d-8ae4-4f42-a759-0f9ed6317e51"
      ,
             "EncryptionEnabled"
      : false
      ,
             "Password"
      : ""
      ,
             "NetworkDrives"
      : ""
      ,
             "BackupVaultId"
      : "af8d111d-8ae4-4f42-a759-0f9ed6317e51"
         }
      }
  }
    
```

### Command Event: StopRestore

 

| **Verb** | **Event**   | **Description**                                          |
| -------- | ----------- | -------------------------------------------------------- |
| POST     | StopRestore | Notify the agent to stop a restore currently in progress |

 

```
  {
      "Event"
      :
      "StopRestore"
      ,
      "Data"
      : {
        "RestoreId" : 1
      ,
        "BackupConfigurationId"
      : 234
      }
  }
    
```

### Raised Event: RestoreInProgress

 

| **Verb** | **Event**         | **Description**                                              |
| -------- | ----------------- | ------------------------------------------------------------ |
| GET      | RestoreInProgress | Inform subscribers that the restore is in progress. Submitted by the agent |

 

```
  {
      "Event"
      :
      "RestoreInProgress"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "RestoreId" : 1
      ,
        "BackupConfigurationId" : 2
      }
  }
    
```

### Raised Event: RestoreProgress

 

| **Verb** | **Event**       | **Description**                                              |
| -------- | --------------- | ------------------------------------------------------------ |
| GET      | RestoreProgress | Inform the subscribers the progress of a restore. Submitted by the agent |

 

```
  {
      "Event"
      :
      "RestoreProgress"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "RestoreId" : 1
      ,
        "BackupConfigurationId" : 2
      ,
        "BytesCompleted" : 1024
      ,
        "BytesRemaining" : 9934
      ,
        "BytesTotal" : 10958
      }
  }
    
```

### Raised Event: RestoreCompleted

 

| **Verb** | **Event**        | **Description**                                              |
| -------- | ---------------- | ------------------------------------------------------------ |
| GET      | RestoreCompleted | Inform the subscribers that a restore has completed. Submitted by the agent |

 

```
  {
      "Event"
      :
      "RestoreCompleted"
      ,
      "MachineAgentId" : 100213
      ,
      "Succeeded" : true
      ,
      "Data"
      : {
        "RestoreId"
      : 1
      ,
        "BackupConfigurationId" : 2
      }     
  }
    
```

### Raised Event: RestoreFailed

 

| **Verb** | **Event**     | **Description**                                  |
| -------- | ------------- | ------------------------------------------------ |
| GET      | RestoreFailed | Inform the subscribers that a restore has failed |

 

```
  {
      "Event"
      :
      "RestoreFailed"
      ,
      "Data"
      : {
         "RestoreId"
      : 1
      ,
         "BackupConfigurationId" : 2
      ,
         "FailedTime" : "2011-04-08 13:25:29"
      }
  }
    
```

### Raised Event: RestoreStopped

 

| **Verb** | **Event**      | **Description**                                   |
| -------- | -------------- | ------------------------------------------------- |
| GET      | RestoreStopped | Inform the subscribers that a restore has stopped |

 

```
  {
      "Event"
      :
      "RestoreStopped"
      ,
      "Data"
      : {
         "RestoreId"
      : 1
      ,
         "BackupConfigurationId" : 2
      ,
         "StoppedTime" : "2011-04-08 13:25:29"
      }
  }
    
```

### Command Event: RequestLogs

 

| **Verb** | **Event**   | **Description**                       |
| -------- | ----------- | ------------------------------------- |
| POST     | RequestLogs | Instruct the agent to submit its logs |

 

```
    {
        "Event": "RequestLogs",
        "RequestId": "46efe87a-553a-49cf-9fe4-5e02c125003c",
        "Succeeded": true,
        "Data": {
            "RequestId": "46efe87a-553a-49cf-9fe4-5e02c125003c",
            "UploadPath": "https://storage101.dfw1.clouddrive.com/v1/MossoCloudFS_246ca22a-97a6-4bf5-83c8-a927420c2d30/AgentLogs/7c8c327e-8846-41a3-9be1-df33a4830fbe.gz?temp_url_sig=5a75b7e02e1c11141bcea6a9de510f6007fe9026&temp_url_expires=1413374983"
        },
        "MachineAgentId": "202780"
    }
```

 

### Raised Event: LogUploadStarted

 

 

| **Verb** | **Event**        | **Description**                               |
| -------- | ---------------- | --------------------------------------------- |
| GET      | LogUploadStarted | Inform subscribers the log upload has started |

 

```
    {
        "Event": "LogUploadStarted",
        "RequestId": "298e3192-4efc-4608-8158-517029a0016e",
        "Succeeded": true,
        "Data": {
            "RequestId": "46efe87a-553a-49cf-9fe4-5e02c125003c",
            "UploadPath": null
        },
        "MachineAgentId": "202780"
    }
```

### Raised Event: LogUploadFinished

  

| **Verb** | **Event**         | **Description**                                |
| -------- | ----------------- | ---------------------------------------------- |
| GET      | LogUploadFinished | Inform subscribers the log upload has finished |

 

```
    {
        "Event": "LogUploadFinished",
        "RequestId": "c65e6739-3d75-4176-968b-5584f0c819b1",
        "Succeeded": true,
        "Data": {
            "RequestId": "46efe87a-553a-49cf-9fe4-5e02c125003c",
            "UploadPath": null
        },
        "MachineAgentId": "202780"
    }
```

 



