from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.slider import Slider
from kivy.uix.progressbar import ProgressBar
from kivy.uix.popup import Popup
from kivy.uix.filechooser import FileChooserListView
from kivy.clock import Clock
from kivy.core.audio import SoundLoader
from kivy.graphics import Color
import os
import time
import random

try:
    from jnius import autoclass
    HAS_JNIUS = True
except:
    HAS_JNIUS = False


class BabyMonitor(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'
        self.padding = 20
        self.spacing = 15
        
        self.noise_threshold = 500
        self.current_noise_level = 0
        self.is_playing = False
        self.is_monitoring = True
        self.mic = None
        self.mic_buffer = None
        self.lullaby = None
        self.current_sound_file = 'mother_voice.wav'
        
        self.noise_start_time = None
        self.play_start_time = None
        self.last_play_end_time = 0
        
        self.grace_period = 1.0
        self.min_play_duration = 100.0
        self.cooldown_period = 10.0
        
        self.title_label = Label(text="[b]MehreJarf[/b]", font_size='28sp', markup=True, size_hint_y=0.08)
        self.add_widget(self.title_label)
        
        self.status_label = Label(text="Starting...", font_size='18sp', markup=True, size_hint_y=0.08)
        self.add_widget(self.status_label)
        
        self.mode_label = Label(text="", font_size='13sp', color=(1, 0.8, 0, 1), size_hint_y=0.05)
        self.add_widget(self.mode_label)
        
        self.noise_label = Label(text="Noise Level: 0", font_size='14sp', size_hint_y=0.06)
        self.add_widget(self.noise_label)
        
        self.noise_bar = ProgressBar(max=1000, value=0, size_hint_y=0.06)
        with self.noise_bar.canvas:
            Color(0.2, 0.8, 0.2, 1)
        self.add_widget(self.noise_bar)
        
        self.timer_label = Label(text="", font_size='12sp', color=(0.5, 0.5, 0.5, 1), size_hint_y=0.04)
        self.add_widget(self.timer_label)
        
        self.threshold_label = Label(text="Sensitivity: 500", font_size='14sp', size_hint_y=0.06)
        self.add_widget(self.threshold_label)
        
        self.sensitivity_slider = Slider(min=100, max=1000, value=500, step=10, size_hint_y=0.06)
        self.sensitivity_slider.bind(value=self.on_sensitivity_change)
        self.add_widget(self.sensitivity_slider)
        
        self.file_button = Button(text="Choose Sound File", font_size='16sp', background_color=(0.3, 0.5, 0.9, 1), color=(1, 1, 1, 1), size_hint_y=0.1)
        self.file_button.bind(on_press=self.open_file_chooser)
        self.add_widget(self.file_button)
        
        self.file_label = Label(text="Sound: mother_voice.wav", font_size='12sp', color=(0.7, 0.7, 0.7, 1), size_hint_y=0.05)
        self.add_widget(self.file_label)
        
        self.toggle_button = Button(text="STOP MONITORING", font_size='16sp', background_color=(0.9, 0.2, 0.2, 1), color=(1, 1, 1, 1), size_hint_y=0.1)
        self.toggle_button.bind(on_press=self.toggle_monitoring)
        self.add_widget(self.toggle_button)
        
        self.help_label = Label(text="MehreJarf v2.2 | pyjnius mic", font_size='11sp', color=(0.5, 0.5, 0.5, 1), size_hint_y=0.04)
        self.add_widget(self.help_label)
        
        self.load_sound()
        self.start_microphone()
    
    def load_sound(self):
        if os.path.exists(self.current_sound_file):
            try:
                self.lullaby = SoundLoader.load(self.current_sound_file)
                self.file_label.text = f"Sound: {os.path.basename(self.current_sound_file)} ✓"
            except:
                self.file_label.text = "Sound: Error"
        else:
            self.file_label.text = "Sound: File not found!"
    
    def open_file_chooser(self, instance):
        was_monitoring = self.is_monitoring
        self.is_monitoring = False
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        file_chooser = FileChooserListView(path='/storage/emulated/0', filters=['*.wav', '*.mp3', '*.ogg', '*.m4a'], size_hint_y=0.8)
        content.add_widget(file_chooser)
        buttons = BoxLayout(size_hint_y=0.2, spacing=10)
        cancel_btn = Button(text="Cancel", background_color=(0.7, 0.7, 0.7, 1))
        select_btn = Button(text="Select", background_color=(0.2, 0.7, 0.2, 1))
        buttons.add_widget(cancel_btn)
        buttons.add_widget(select_btn)
        content.add_widget(buttons)
        self.popup = Popup(title="Choose Sound File", content=content, size_hint=(0.9, 0.8))
        cancel_btn.bind(on_press=self.popup.dismiss)
        select_btn.bind(on_press=lambda x: self.select_file(file_chooser))
        self.popup.bind(on_dismiss=lambda x: self.resume_monitoring(was_monitoring))
        self.popup.open()
    
    def select_file(self, file_chooser):
        if file_chooser.selection:
            selected = file_chooser.selection[0]
            if selected.lower().endswith(('.wav', '.mp3', '.ogg', '.m4a')):
                if self.is_playing:
                    self.stop_lullaby()
                self.current_sound_file = selected
                self.load_sound()
        self.popup.dismiss()
    
    def resume_monitoring(self, was_monitoring):
        self.is_monitoring = was_monitoring
    
    def start_microphone(self):
        if HAS_JNIUS:
            try:
                AudioRecord = autoclass('android.media.AudioRecord')
                AudioFormat = autoclass('android.media.AudioFormat')
                AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
                
                sample_rate = 44100
                channel_config = AudioFormat.CHANNEL_IN_MONO
                audio_format = AudioFormat.ENCODING_PCM_16BIT
                buffer_size = AudioRecord.getMinBufferSize(sample_rate, channel_config, audio_format)
                
                if buffer_size < 1024:
                    buffer_size = 1024
                
                self.mic = AudioRecord(AudioSource.MIC, sample_rate, channel_config, audio_format, buffer_size)
                
                if self.mic.getState() == 1:
                    self.mic.startRecording()
                    self.mic_buffer = buffer_size
                    Clock.schedule_interval(self.check_real_sound, 0.1)
                    self.status_label.text = "[color=00FF00]●[/color]  Microphone active (pyjnius)"
                    return
                else:
                    raise Exception("AudioRecord init failed")
                    
            except Exception as e:
                self.status_label.text = f"[color=FFA500]●[/color]  pyjnius error: {str(e)[:30]}"
        else:
            self.status_label.text = "[color=FFA500]●[/color]  pyjnius not installed"
        
        Clock.schedule_interval(self.check_fake_sound, 0.3)
    
    def check_real_sound(self, dt):
        if not self.is_monitoring or self.mic is None:
            return
        try:
            ShortBuffer = autoclass('java.nio.ShortBuffer')
            buffer = ShortBuffer.allocate(self.mic_buffer // 2)
            read = self.mic.read(buffer, self.mic_buffer)
            
            if read > 0:
                total = 0.0
                limit = min(read, self.mic_buffer // 2)
                for i in range(limit):
                    total += abs(buffer.get(i))
                avg = (total / limit) * 0.05
                self.process_noise_level(avg)
        except:
            pass
    
    def check_fake_sound(self, dt):
        if not self.is_monitoring:
            return
        noise = random.randint(0, 1000)
        self.process_noise_level(noise)
    
    def should_start_playing(self):
        now = time.time()
        if self.is_playing:
            return False
        if now - self.last_play_end_time < self.cooldown_period:
            remaining = self.cooldown_period - (now - self.last_play_end_time)
            self.mode_label.text = f"Cooling down... {remaining:.0f}s remaining"
            return False
        if self.noise_start_time is None:
            self.noise_start_time = now
            return False
        noise_duration = now - self.noise_start_time
        if noise_duration >= self.grace_period:
            self.mode_label.text = ""
            return True
        else:
            self.mode_label.text = f"Detecting... {noise_duration:.1f}s / {self.grace_period}s"
            return False
    
    def should_stop_playing(self):
        now = time.time()
        if not self.is_playing:
            return False
        if self.play_start_time is not None:
            play_duration = now - self.play_start_time
            if play_duration < self.min_play_duration:
                remaining = self.min_play_duration - play_duration
                self.mode_label.text = f"Playing... min {remaining:.0f}s more"
                return False
        return True
    
    def process_noise_level(self, noise_level):
        self.current_noise_level = noise_level
        now = time.time()
        self.noise_bar.value = min(noise_level, 1000)
        self.noise_label.text = f"Noise Level: {noise_level:.0f}"
        
        if noise_level > self.noise_threshold:
            with self.noise_bar.canvas:
                Color(1, 0.2, 0.2, 1)
        else:
            ratio = noise_level / self.noise_threshold if self.noise_threshold > 0 else 0
            if ratio > 0.7:
                with self.noise_bar.canvas:
                    Color(1, 0.6, 0, 1)
            else:
                with self.noise_bar.canvas:
                    Color(0.2, 0.8, 0.2, 1)
        
        if not self.is_monitoring:
            return
        
        is_loud = noise_level > self.noise_threshold
        if is_loud:
            if self.noise_start_time is None:
                self.noise_start_time = now
            if self.should_start_playing():
                self.play_lullaby()
        else:
            self.noise_start_time = None
            if self.should_stop_playing():
                self.stop_lullaby()
        
        if self.is_playing and self.play_start_time:
            elapsed = now - self.play_start_time
            self.timer_label.text = f"Playing for: {elapsed:.0f}s"
        elif not self.is_playing:
            self.timer_label.text = ""
    
    def play_lullaby(self):
        if self.lullaby and not self.is_playing:
            try:
                self.lullaby.play()
                self.is_playing = True
                self.play_start_time = time.time()
                self.noise_start_time = None
                self.status_label.text = "[color=FF0000]●[/color]  Baby crying! Playing..."
                self.mode_label.text = ""
            except:
                pass
    
    def stop_lullaby(self):
        if self.lullaby and self.is_playing:
            try:
                self.lullaby.stop()
                self.is_playing = False
                self.last_play_end_time = time.time()
                self.play_start_time = None
                self.noise_start_time = None
                self.status_label.text = "[color=00FF00]●[/color]  Monitoring..."
                self.mode_label.text = ""
            except:
                pass
    
    def on_sensitivity_change(self, instance, value):
        self.noise_threshold = int(value)
        self.threshold_label.text = f"Sensitivity: {self.noise_threshold}"
    
    def toggle_monitoring(self, instance):
        if self.is_monitoring:
            self.is_monitoring = False
            self.toggle_button.text = "START MONITORING"
            self.toggle_button.background_color = (0.2, 0.8, 0.2, 1)
            self.status_label.text = "[color=FFA500]●[/color]  Paused"
            self.mode_label.text = ""
            if self.is_playing:
                self.stop_lullaby()
        else:
            self.is_monitoring = True
            self.toggle_button.text = "STOP MONITORING"
            self.toggle_button.background_color = (0.9, 0.2, 0.2, 1)
            self.status_label.text = "[color=00FF00]●[/color]  Monitoring..."
            self.noise_start_time = None
    
    def on_stop(self):
        try:
            if self.mic:
                self.mic.stop()
                self.mic.release()
        except:
            pass


class BabyApp(App):
    def build(self):
        return BabyMonitor()


if __name__ == '__main__':
    BabyApp().run()