import pygame
import json
import os
import random
import math

# --- 초기 설정 ---
pygame.init()
BASE_PATH = r"C:\Users\gwangjin\Desktop\personal\cat_game"
CAT_JSON_PATH = os.path.join(BASE_PATH, "cat.json")
CAT_IMG_PATH = os.path.join(BASE_PATH, "cat.png")
OBJECTS_JSON_PATH = os.path.join(BASE_PATH, "objects.json")
OBJECTS_IMG_PATH = os.path.join(BASE_PATH, "objects.png")
BG_PATH = os.path.join(BASE_PATH, "background.png")
TABLE_MASK_PATH = os.path.join(BASE_PATH, "table_mask.png")
FLOOR_MASK_PATH = os.path.join(BASE_PATH, "floor_mask.png")

temp_bg = pygame.image.load(BG_PATH)
SCREEN_WIDTH, SCREEN_HEIGHT = temp_bg.get_width() * 3, temp_bg.get_height() * 3
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Cat Dropping Things")
clock = pygame.time.Clock()
background_img = pygame.transform.scale(temp_bg.convert(), (SCREEN_WIDTH, SCREEN_HEIGHT))

# 사운드 로드
pygame.mixer.init()
push_sound = pygame.mixer.Sound(os.path.join(BASE_PATH, "push.wav"))
fast_push_sound = pygame.mixer.Sound(os.path.join(BASE_PATH, "fast_push.wav"))

def load_and_scale_mask(path, scale=3):
    img = pygame.image.load(path).convert_alpha()
    scaled_img = pygame.transform.scale(img, (img.get_width() * scale, img.get_height() * scale))
    return pygame.mask.from_threshold(scaled_img, (255, 255, 255, 255), (1, 1, 1, 255))

table_mask = load_and_scale_mask(TABLE_MASK_PATH)
floor_mask = load_and_scale_mask(FLOOR_MASK_PATH)

def load_spritesheet(json_path, img_path, scale=3):
    with open(json_path, 'r') as f:
        data = json.load(f)
    sheet = pygame.image.load(img_path).convert_alpha()
    frames = []
    import re
    def extract_num(s):
        nums = re.findall(r'\d+', s)
        return int(nums[-1]) if nums else 0
    frame_names = sorted(data['frames'].keys(), key=extract_num)
    for name in frame_names:
        info = data['frames'][name]
        f = info['frame']
        rect = pygame.Rect(f['x'], f['y'], f['w'], f['h'])
        image = pygame.Surface(rect.size, pygame.SRCALPHA)
        image.blit(sheet, (0, 0), rect)
        image = pygame.transform.scale(image, (f['w'] * scale, f['h'] * scale))
        frames.append(image)
    return frames

def draw_shadow(surface, center_x, bottom_y, width, height, alpha=100):
    shadow_w = width * 0.7
    shadow_h = height * 0.15
    shadow_surface = pygame.Surface((shadow_w, shadow_h), pygame.SRCALPHA)
    pygame.draw.ellipse(shadow_surface, (50, 50, 50, alpha), (0, 0, shadow_w, shadow_h))
    surface.blit(shadow_surface, (center_x - shadow_w//2, bottom_y - shadow_h//2))

cat_frames = load_spritesheet(CAT_JSON_PATH, CAT_IMG_PATH, 3)
obj_frames = load_spritesheet(OBJECTS_JSON_PATH, OBJECTS_IMG_PATH, 3)

class GameObject:
    def __init__(self, x, y, frame_idx):
        self.image = obj_frames[frame_idx]
        self.rect = self.image.get_rect(midbottom=(x, y))
        self.state = "TABLE"
        self.vel_y = 0
        self.rotation = 0
        self.rot_vel = 0
        self.is_dragged = False

    def update(self):
        if self.is_dragged:
            self.rect.midbottom = pygame.mouse.get_pos()
            self.state = "TABLE"; self.vel_y = 0; self.rotation = 0
            return
        if self.state == "TABLE":
            pos = self.rect.midbottom
            if not (0 <= pos[0] < SCREEN_WIDTH and 0 <= pos[1] < SCREEN_HEIGHT) or not table_mask.get_at(pos):
                self.state = "FALLING"; self.rot_vel = random.uniform(-8, 8)
        elif self.state == "FALLING":
            self.vel_y += 0.6; self.rect.y += self.vel_y; self.rotation += self.rot_vel
            pos = self.rect.midbottom
            if 0 <= pos[0] < SCREEN_WIDTH and 0 <= pos[1] < SCREEN_HEIGHT:
                if floor_mask.get_at(pos):
                    if self.vel_y > 2: self.vel_y *= -0.4; self.rot_vel *= 0.5
                    else: self.state = "FLOOR"; self.vel_y = 0; self.rot_vel = 0

    def draw(self, surface):
        shadow_y = self.rect.bottom if self.state != "FALLING" else 540
        draw_shadow(surface, self.rect.centerx, shadow_y, self.rect.width, self.rect.height)
        img = self.image
        if self.rotation != 0:
            img = pygame.transform.rotate(self.image, self.rotation)
        surface.blit(img, img.get_rect(midbottom=self.rect.midbottom))

class Cat:
    def __init__(self):
        self.x, self.y = 450, 300
        self.target_x, self.target_y = self.x, self.y
        self.state = "IDLE" 
        self.facing_right = True
        self.frame_timer = 0
        self.anim_idx = 0
        self.current_frame = 4 
        self.wait_timer = 0
        self.action_cooldown = pygame.time.get_ticks() + 1000
        self.next_stretch_time = 0
        self.next_look_time = 0
        self.speed = 0.6
        self.boost_mode = False # 부스트 모드 상태

    # 부스트 모드용 시간 multiplier
    def _t(self, ms):
        return int(ms * (0.5 if self.boost_mode else 1.0))

    def set_state(self, new_state):
        if self.state != new_state:
            self.state = new_state
            self.anim_idx = 0; self.frame_timer = 0; self.wait_timer = 0
            frames = self.get_anim_frames()
            self.current_frame = frames[0]
            
            # 사운드 재생
            if new_state == "PUSH":
                push_sound.play()
            elif new_state == "FAST_PUSH":
                fast_push_sound.play()

    def get_anim_frames(self):
        if self.state in ["IDLE", "PRE_PUSH"]: return [4]
        if self.state == "PATROL": return [10, 11]
        if self.state == "WATCH": return [4, 5, 6, 5, 4]
        if self.state == "STRETCH": return [6, 7, 8, 9]
        if self.state in ["PUSH", "FAST_PUSH"]: return [0, 1, 2, 3]
        return [4]

    def update(self, objects):
        now = pygame.time.get_ticks()
        img = cat_frames[self.current_frame]
        if not self.facing_right: img = pygame.transform.flip(img, True, False)
        cat_rect = img.get_rect(midbottom=(self.x, self.y))
        cat_mask = pygame.mask.from_surface(img)
        m_pos = pygame.mouse.get_pos()
        m_rel_pos = (m_pos[0] - cat_rect.x, m_pos[1] - cat_rect.y)
        is_mouseover = False
        if cat_rect.collidepoint(m_pos) and 0 <= m_rel_pos[0] < cat_mask.get_size()[0] and 0 <= m_rel_pos[1] < cat_mask.get_size()[1]:
            if cat_mask.get_at(m_rel_pos): is_mouseover = True

        if self.state not in ["PUSH", "FAST_PUSH", "STRETCH", "PRE_PUSH"]:
            if is_mouseover:
                if self.state != "WATCH" and self.state != "IDLE": self.set_state("IDLE")
                if now > self.next_stretch_time and random.random() < 0.005:
                    self.set_state("STRETCH"); self.next_stretch_time = now + self._t(15000)
                elif now > self.next_look_time:
                    self.set_state("WATCH"); self.next_look_time = now + self._t(random.randint(5000, 10000))
            else:
                if self.state in ["IDLE", "WATCH"] and self.wait_timer == 0:
                    if now > self.action_cooldown: self.set_state("PATROL")

        if self.state == "PRE_PUSH":
            if is_mouseover: 
                self.set_state("IDLE")
            elif now > self.wait_timer: 
                self.set_state("PUSH")

        # 애니메이션 속도 및 프레임 처리
        frames = self.get_anim_frames()
        fps = 4.5
        if self.state == "PATROL": fps = 3
        if self.state == "WATCH": fps = 1.4
        if self.state == "STRETCH": fps = 2.1
        if self.state == "PUSH": fps = 5.6
        if self.state == "FAST_PUSH": fps = 15
        
        # 기지개 마지막 프레임 대기 (부스트 시 절반)
        if self.state == "STRETCH" and self.current_frame == 9:
            if self.wait_timer == 0: self.wait_timer = now
            if now - self.wait_timer < self._t(2000): return
            else: self.wait_timer = 0; self.set_state("IDLE"); return

        self.frame_timer += clock.get_time()
        if self.frame_timer > 1000 / fps:
            self.frame_timer = 0
            self.anim_idx += 1
            if self.anim_idx >= len(frames):
                if self.state in ["PATROL", "IDLE"]: self.anim_idx = 0
                elif self.state == "WATCH": self.set_state("IDLE")
                elif self.state in ["PUSH", "FAST_PUSH"]: self.set_state("IDLE")
                else: self.anim_idx = len(frames) - 1
            self.current_frame = frames[min(self.anim_idx, len(frames)-1)]

        if self.state == "PATROL":
            if math.hypot(self.target_x - self.x, self.target_y - self.y) < 10:
                # 대기시간 부스트 적용
                self.action_cooldown = now + self._t(random.randint(333, 1333))
                self.set_state("IDLE")
                target_obj = None
                for obj in objects:
                    if obj.state == "TABLE": target_obj = obj; break
                if target_obj and random.random() < 0.8:
                    offset = 40 if random.random() > 0.5 else -40
                    self.target_x, self.target_y = target_obj.rect.centerx + offset, target_obj.rect.bottom
                else:
                    for _ in range(50):
                        tx, ty = random.randint(100, SCREEN_WIDTH-100), random.randint(100, SCREEN_HEIGHT-100)
                        if 0 <= tx < SCREEN_WIDTH and 0 <= ty < SCREEN_HEIGHT and table_mask.get_at((tx, ty)):
                            self.target_x, self.target_y = tx, ty; break
                return
            angle = math.atan2(self.target_y - self.y, self.target_x - self.x)
            self.x += math.cos(angle) * self.speed
            self.y += math.sin(angle) * self.speed
            self.facing_right = (self.target_x > self.x)
            for obj in objects:
                if self.check_push_area(obj) and random.random() < 0.2: 
                    self.set_state("PRE_PUSH")
                    # 유예시간 부스트 적용
                    self.wait_timer = now + self._t(random.randint(266, 800))
                    break

        if self.state in ["PUSH", "FAST_PUSH"] and self.anim_idx == 2:
            for obj in objects:
                if self.check_push_area(obj):
                    obj.rect.x += 15 if self.facing_right else -15; obj.state = "FALLING"

    def check_push_area(self, obj):
        if obj.state != "TABLE" or obj.is_dragged: return False
        rel_x, rel_y = obj.rect.centerx - self.x, obj.rect.bottom - self.y
        w_lim, h_lim = 192 * 0.4, 192 * 0.2
        if self.facing_right: return 0 < rel_x < w_lim and -h_lim < rel_y < h_lim
        else: return -w_lim < rel_x < 0 and -h_lim < rel_y < h_lim

    def draw(self, surface):
        draw_shadow(surface, self.x, self.y + 5, 160, 160)
        img = cat_frames[self.current_frame]
        if not self.facing_right: img = pygame.transform.flip(img, True, False)
        surface.blit(img, img.get_rect(midbottom=(self.x, self.y)))

cat = Cat()
objects = []
for i in range(8):
    for _ in range(200):
        rx, ry = random.randint(100, SCREEN_WIDTH-100), random.randint(200, 450)
        if 0 <= rx < SCREEN_WIDTH and 0 <= ry < SCREEN_HEIGHT and table_mask.get_at((rx, ry)):
            objects.append(GameObject(rx, ry, random.randint(0, len(obj_frames)-1))); break

running = True
while running:
    clock.tick(60)
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        elif event.type == pygame.MOUSEBUTTONDOWN:
            for obj in reversed(objects):
                if obj.rect.collidepoint(event.pos):
                    obj.is_dragged = True; break
        elif event.type == pygame.MOUSEBUTTONUP:
            for obj in objects:
                if obj.is_dragged:
                    obj.is_dragged = False
                    if 0 <= obj.rect.centerx < SCREEN_WIDTH and 0 <= obj.rect.bottom < SCREEN_HEIGHT and table_mask.get_at(obj.rect.midbottom):
                        obj.state = "TABLE"
                    else: obj.state = "FALLING"
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_s:
                for obj in objects:
                    if cat.check_push_area(obj):
                        cat.set_state("FAST_PUSH"); break
            elif event.key == pygame.K_b:
                cat.boost_mode = not cat.boost_mode
    cat.update(objects)
    for obj in objects: obj.update()
    screen.blit(background_img, (0, 0))
    for obj in objects: obj.draw(screen)
    cat.draw(screen)
    pygame.display.flip()
pygame.quit()
