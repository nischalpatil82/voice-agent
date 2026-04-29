import os

file_path = r"C:\Users\User\Desktop\JB-Portal-dev-2\src\app\components\widgets\voice-assistant\voice-assistant.ts"
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

import_str = "import { io, Socket } from 'socket.io-client';\n"
if "socket.io-client" not in content:
    content = content.replace("import { Component", import_str + "import { Component")

content = content.replace("private sessionId: string = '';\n", "private sessionId: string = '';\n  private socket: Socket | null = null;\n")

# Replace ngOnInit
old_ngoninit = """  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      this.initSpeech();
      this.loadSession();
      this.loadMessages();
    }
  }"""
new_ngoninit = """  ngOnInit() {
    if (isPlatformBrowser(this.platformId)) {
      this.initSpeech();
      this.initSocket();
      this.loadSession();
      this.loadMessages();
    }
  }

  private initSocket() {
    this.socket = io(this.API, { transports: ['websocket', 'polling'] });
    this.socket.on('command_result', (data: any) => {
      this.zone.run(() => {
        if (data.session_id) {
          this.sessionId = data.session_id;
          try { localStorage.setItem('va-session-id', this.sessionId); } catch {}
        }
        if (data.text) {
          this.inputText = data.text;
          console.log('Voice command:', data.text, '→', data.intent);
          this.addUser(data.text);
          if (data.message) {
            this.addBot(data.message, data.intent);
            this.speak(data.message);
          }
          if (data.actions?.length) {
            this.runActions(data.actions);
          }
        } else if (data.error) {
          this.addBot(data.error);
        } else {
          this.addBot('Could not understand audio.');
        }
        this.isLoading = false;
      });
    });
  }"""
content = content.replace(old_ngoninit, new_ngoninit)

# Replace startRecording chunks
old_ondata = """      this.mediaRecorder.ondataavailable = (e: any) => {
        if (e.data.size > 0) this.audioChunks.push(e.data);
      };"""
new_ondata = """      this.mediaRecorder.ondataavailable = (e: any) => {
        if (e.data.size > 0) {
           this.audioChunks.push(e.data);
           this.socket?.emit('audio_chunk', { audio: e.data });
        }
      };"""
content = content.replace(old_ondata, new_ondata)

# Change mediaRecorder.start() to .start(250)
content = content.replace("this.mediaRecorder.start();", "this.mediaRecorder.start(250);")

# Replace sendAudioToServer completely
old_send_audio = """  private async sendAudioToServer() {
    if (this.audioChunks.length === 0) return;

    this.zone.run(() => { this.isLoading = true; });

    const audioBlob = new Blob(this.audioChunks, {
      type: this.mediaRecorder?.mimeType || 'audio/webm',
    });
    const frontendContext = this.buildVoiceContext();
    const formData  = new FormData();
    formData.append('audio', audioBlob, 'voice.webm');
    formData.append('page', this.router.url);
    formData.append('context_json', JSON.stringify(frontendContext));

    try {
      const res = await fetch(`${this.API}/voice-command`, {
        method: 'POST',
        headers: { 'X-Session-ID': this.sessionId },
        body:   formData,
        signal: AbortSignal.timeout(60000),
      });
      const data = await res.json();

      this.zone.run(() => {
        if (data.session_id) {
          this.sessionId = data.session_id;
          try { localStorage.setItem('va-session-id', this.sessionId); } catch {}
        }

        if (data.text) {
          this.inputText = data.text;
          console.log('Voice command:', data.text, '→', data.intent);
          this.addUser(data.text);

          if (data.message) {
            this.addBot(data.message, data.intent);
            // TTS — speak the response
            this.speak(data.message);
          }
          if (data.actions?.length) {
            this.runActions(data.actions);
          }
          this.isLoading = false;
        } else if (data.error) {
          this.addBot(data.error || 'Could not understand audio. Please try again.');
          this.isLoading = false;
        } else {
          this.addBot('Could not understand audio. Please try again.');
          this.isLoading = false;
        }
      });
    } catch {
      this.zone.run(() => {
        this.addBot('Could not reach server for transcription.');
        this.isLoading = false;
      });
    }
  }"""

new_send_audio = """  private async sendAudioToServer() {
    if (this.audioChunks.length === 0) return;
    this.zone.run(() => { this.isLoading = true; });
    const frontendContext = this.buildVoiceContext();
    this.socket?.emit('stop_recording', { 
        page: this.router.url, 
        context: frontendContext, 
        session_id: this.sessionId 
    });
  }"""
if old_send_audio in content:
    content = content.replace(old_send_audio, new_send_audio)
else:
    print("Warning: Could not find old sendAudioToServer exact match.")

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print(f"Patched {file_path}")
