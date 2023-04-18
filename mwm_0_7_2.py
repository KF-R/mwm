#!/usr/bin/env python3
## (c) 1985, 2023  Kerry Fraser-Robinson
## A pygame reboot of 'Mining With Mines' (1985) for the ZX Spectrum by the same author.
import os
os.environ['PYGAME_HIDE_SUPPORT_PROMPT'] = "hide"
import pygame, random, sys, math 
from datetime import datetime

pygame.init()
pygame.mixer.init()
WINDOW_SIZE = (800, 600)
screen = pygame.display.set_mode(WINDOW_SIZE)
clock = pygame.time.Clock()

if '_' in os.path.basename(__file__): ## Dev version
    filename = os.path.basename(__file__).split('_')
    VERSION = 'v ' + filename[1] + '.' + filename[2] + '.' + filename[3].replace('.py', '')
else: VERSION = 'v 0.7.2'

IMG_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'data')
if os.path.exists(IMG_DIR):
    sys.path.append(IMG_DIR)
HIGHSCORE_FILENAME = os.path.join(os.getcwd(),'mwm-scores.txt')
ICON_FILE = 'mwm.ico'

if os.path.exists(os.path.join(IMG_DIR, ICON_FILE)):
    icon = pygame.image.load(os.path.join(IMG_DIR,ICON_FILE))
    pygame.display.set_icon(icon)

pygame.display.set_caption('Mining with Mines ' + VERSION)

# Define colors and constants
DIFFICULTY_MULTIPLIER = 4
HIGH_SCORE_LIMIT = 6
DIFF_STRING, DIFFICULTY = ['Easy  ','Medium','Hard  '], 2
BLACK, BROWN, DARK_GREY, WHITE, YELLOW, CYAN = (0, 0, 0), (128, 96, 64), (64, 64, 64), (255, 255, 255), (220,220,20), (16,220,220)
GRID_VERTICAL_OFFSET, GRID_HORIZONTAL_OFFSET = 20, 20
GRID_WIDTH, GRID_HEIGHT, CELL_SIZE, SCROLL_LIMIT, PLAYER_START_POS = 20, 30, 18, 8, (10, 0)
GEM_SCORE, STARTING_JET_FUEL, STARTING_BOMBS, STARTING_SHIELDS, DEATH_TIMEOUT = 50, 40, 5, 4, 500
ROCK_PROB, LOOT_PROB, fall_cycles_per_tick, BOMB_CYCLES_PER_TICK, direction, jet_fuel = 0.3, 0.01, 5, 50, 1, STARTING_JET_FUEL
game_board, bomb_list, loot_list = [[0 for x in range(GRID_WIDTH)] for y in range(GRID_HEIGHT)], [], []
INITIAL_LOOT_TABLE = ['gem_stone', 'package', 'oil_drum', 'high_voltage'] + ['fire'] * ((DIFFICULTY * DIFFICULTY_MULTIPLIER) + DIFFICULTY_MULTIPLIER)
loot_table = INITIAL_LOOT_TABLE
NL, SPRITE_SIZE = "\n", 0.05
FONT_NAME, FPS = '3270Medium.otf', 60
font_cache = {}

player_x, player_y, cycles, death_timer = 10, 0, 0, 0
game_board[player_y][player_x] = 0
score, bombs, shields = 0, STARTING_BOMBS, STARTING_SHIELDS
DIFFICULTY_NOTICE = ' Press 1-3 for difficulty '
status, notice, running = ' Press <SPACE> to start ', DIFFICULTY_NOTICE, False

def set_loot_for_difficulty(lst, new_difficulty: int = 2):
    global loot_table
    loot_table = INITIAL_LOOT_TABLE + [lst[-1]] * new_difficulty * DIFFICULTY_MULTIPLIER
    
## Load all PNG files from the given directory
def load_sprites(img_dir=IMG_DIR):
    sprites = {}
    for file in os.listdir(img_dir):
        if file.endswith('.png'):
            name = os.path.splitext(file)[0]
            path = os.path.join(img_dir, file)
            sprites[name] = pygame.image.load(path).convert_alpha()
    return sprites

def sprite_at(canvas, x: int = 1, y: int = 1, name: str = 'gemstone', scale: float = 1.0):
    if name in sprites:
        image = sprites[name]
        if scale != 1.0:
            width = int(image.get_width() * scale)
            height = int(image.get_height() * scale)
            image = pygame.transform.scale(image, (width, height))
        canvas.blit(image, (x, y))

def print_at(canvas, text_x: int, text_y: int, text_string: str, font_size: int = 16, color = (255,255,255), bgcolor = DARK_GREY):
    global font_cache
    font_key = (FONT_NAME, font_size)
    if font_key not in font_cache:
        font_cache[font_key] = pygame.font.Font(os.path.join(IMG_DIR,FONT_NAME), font_size)
    font = font_cache[font_key]
    text = font.render(str(text_string), True, color, bgcolor)
    canvas.blit(text, (text_x, text_y))

def populate_board():
    """ Create ground according to probability, ensuring two gaps where player is and immediately below """
    for y in range(2,GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            game_board[y][x] = 1 if random.random() < ROCK_PROB else 0
    game_board[player_y][player_x],game_board[player_y+1][player_x] = 0,0

def scroll_up():
    global game_board, bomb_list, loot_list
    new_line = [1 if random.random() < ROCK_PROB else 0 for x in range(GRID_WIDTH)]
    game_board.pop(0)
    game_board.append(new_line)
    bomb_list = [(y-1,x,t) for y,x,t in bomb_list if y > 0]
    loot_list = [(y-1,x,t) for y,x,t in loot_list if y > 0]
    loot_list += [(GRID_HEIGHT-1,i,min(4,random.randint(0, len(loot_table)))) for i, content in enumerate(new_line) if content == 0 and random.random() < LOOT_PROB]

def boom(y, x):
    """ Blow up a bomb """
    global game_board, player_y, player_x, shields, bombs, status, notice, running
    boom_sound.play()
    for i, j in ((i, j) for i in range(y-1, y+2) for j in range(x-1, x+2) if 0 <= i < len(game_board) and 0 <= j < len(game_board[0])):
        game_board[i][j] = 0
    if abs(player_x - x) + abs(player_y - y) < 2:
        if shields > 0: 
            shields -= 1
            spark_sound.play()
        else: 
            running, bombs, status, notice = False, 0, " Press <SPACE> to retry ", DIFFICULTY_NOTICE
            high_score_table(score)
            pygame.time.delay(500)
            outro_tune.play()

def press_a_key():
    global DIFFICULTY
    key_pressed = False
    while not key_pressed:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
                key_pressed = True
                if event.key == pygame.K_1: DIFFICULTY = 1
                elif event.key == pygame.K_2: DIFFICULTY = 2
                elif event.key == pygame.K_3: DIFFICULTY = 3
                set_loot_for_difficulty(loot_table, DIFFICULTY - 1)
                break

def display_flag_sprites(canvas, start_x: int = 10, start_y: int = 10, padding: int = 10, scale: float = 1.0):
    x = start_x
    y = start_y
    flag_sprites = [sprite_name for sprite_name in sprites if 'flag_' in sprite_name]
    flag_sprites.reverse()
    for sprite_name in flag_sprites:
        sprite_at(canvas, x, y, sprite_name, scale)
        width = sprites[sprite_name].get_width() * scale
        x += width + padding

def display_high_scores(screen, high_scores, x, y, col_width, row_height, color=WHITE, bgcolor=BLACK, with_date: bool = True):
    DATE_OFFSET = 60
    # Split the input string into rows and then into columns
    rows = [row.split(',') for row in high_scores.strip().split('\n')]
    rows.insert(1, '')
    # Render and display text for each row and column
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            if r == 0 and c == 3:  # Date offset for table headline tidiness
                if with_date: print_at(screen, x + c * col_width + DATE_OFFSET, y + r * row_height, value.capitalize(), row_height, color, bgcolor)
            else:
                if r == 0:
                    value = value.capitalize()
                if c!=3 or with_date: print_at(screen, x + c * col_width, y + r * row_height, value, row_height, color, bgcolor)

def ordinal(n): return format(abs(n), ",") + ("th" if 4 <= abs(n) % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(abs(n) % 10, "th"))

def high_score_table(score):
    # Get the system username and the current date
    DEFAULT_HEADLINE = 'name,score,difficulty,date'
    username = os.environ.get('USERNAME') or os.environ.get('USER')
    now = datetime.now()
    date_string = f"{ordinal(now.day)} {now.strftime('%b')} {now.strftime('%-I:%M%p').lower()}"
    # Check if the file exists
    if os.path.exists(HIGHSCORE_FILENAME):
        with open(HIGHSCORE_FILENAME, "r") as file:
            content = file.readlines()
            if(score==0):
                return "".join(content).strip() # We're just reading
    else:
        # If it doesn't exist, create it and add the first line
        with open(HIGHSCORE_FILENAME, "w") as file:
            file.write(DEFAULT_HEADLINE + NL)
            content = [DEFAULT_HEADLINE + NL]
    
    # Parse comma separated lines into a list of tuples
    scores = [tuple(line.strip().split(',')) for line in content[1:]]
    
    # Insert the new score into the right location
    new_score = (username, str(score), DIFF_STRING[DIFFICULTY-1], date_string)
    inserted = False
    for i, existing_score in enumerate(scores):
        if score > int(existing_score[1]):
            scores.insert(i, new_score)
            inserted = True
            break
    
    if not inserted:
        scores.append(new_score)
    
    if(len(scores) >= HIGH_SCORE_LIMIT):
        scores = scores[:HIGH_SCORE_LIMIT]
    
    # Update the file
    with open(HIGHSCORE_FILENAME, "w") as file:
        file.write(DEFAULT_HEADLINE + NL)
        for score in scores:
            file.write(','.join(score) + NL)
    
    # Return the entire score table as a string
    result = DEFAULT_HEADLINE + NL + NL.join([','.join(score) for score in scores])
    # print(result)
    return result

def draw_death_clock(screen, x, y, radius: int = 32, value: int = 0, value_range: int = 60):
    center = (x, y)
    clock_color = DARK_GREY
    filled_arc_color = (172, 48, 16)

    # Draw the circle
    pygame.draw.circle(screen, clock_color, center, radius)

    # Calculate the angle for the second hand
    second_angle = (value % value_range) * 2 * math.pi / value_range + math.pi / 2

    # Draw the filled arc
    num_segments = int(radius * (second_angle - math.pi / 2) / (2 * math.pi))
    num_segments = max(num_segments, 1)
    vertices = [center]

    for i in range(num_segments + 1):
        angle = math.pi / 2 - i * (second_angle - math.pi / 2) / num_segments
        x = center[0] + radius * math.cos(angle)
        y = center[1] - radius * math.sin(angle)
        vertices.append((x, y))

    pygame.draw.polygon(screen, filled_arc_color, vertices)

## Prepare audio and sprites
intro_tune = pygame.mixer.Sound(os.path.join(IMG_DIR,'intro.wav'))
outro_tune = pygame.mixer.Sound(os.path.join(IMG_DIR,'outro.wav'))
boom_sound = pygame.mixer.Sound(os.path.join(IMG_DIR,'boom.wav'))
bling_sound = pygame.mixer.Sound(os.path.join(IMG_DIR,'bling.wav'))
spark_sound = pygame.mixer.Sound(os.path.join(IMG_DIR,'spark.wav'))
crunch_sound = pygame.mixer.Sound(os.path.join(IMG_DIR,'crunch.wav'))
sprites = load_sprites()

## Intro
print_at(screen,280,20,' M W M ', 64, YELLOW, BLACK)
print_at(screen,340,80, ' ' + VERSION + ' ', 24, YELLOW, BLACK)
print_at(screen,24,350,' <press any key to continue> ', 48, CYAN, BLACK)
print_at(screen,312,575,' \u00A9 2023  KFR ', 24, WHITE, BLACK)
display_flag_sprites(screen,30,460,1,0.2)
if notice != '': print_at(screen, 230, 420, notice, 24, WHITE, BLACK)
display_high_scores(screen, high_score_table(0), 40, 140, 150, 24)
pygame.display.update()
intro_tune.play()
pygame.time.delay(1000)
press_a_key()

## Main game loop
populate_board()
while True:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: pygame.quit(); sys.exit()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE: pygame.quit(); sys.exit()
            if not running:
                if event.key == pygame.K_SPACE or event.key == pygame.K_1 or event.key == pygame.K_2 or event.key==pygame.K_3:
                    if event.key == pygame.K_1: DIFFICULTY = 1
                    elif event.key == pygame.K_2: DIFFICULTY = 2
                    elif event.key == pygame.K_3: DIFFICULTY = 3
                    set_loot_for_difficulty(loot_table, DIFFICULTY - 1)
                    if score==0:
                        ## Start a new game
                        running, status = True, ''
                    else:
                        ## Reset and restart a new game 
                        player_y = PLAYER_START_POS[1]; player_x = PLAYER_START_POS[0]
                        populate_board()
                        score, shields, bombs, jet_fuel, running, status = 0, STARTING_SHIELDS, STARTING_BOMBS, STARTING_JET_FUEL, True, ''
                        intro_tune.play()
                        pygame.time.delay(1000)
                else:
                    continue
            ## Game is running so we should interpret player actions 
            if event.key == pygame.K_j and player_x > 0 and game_board[player_y][player_x - 1] == 0: player_x -= 1
            elif event.key == pygame.K_l and player_x < GRID_WIDTH - 1 and game_board[player_y][player_x + 1] == 0: player_x += 1
            elif event.key == pygame.K_k:
                if player_y > 0 and bombs > 0:  
                    bomb_list.append((player_y, player_x, 3))
                    bombs -= 1
            elif event.key == pygame.K_i:
                if jet_fuel > 0:
                    direction = direction * - 1
                    crunch_sound.play()

    ## Draw the game board
    screen.fill(BLACK)
    pygame.draw.rect(screen,DARK_GREY,pygame.Rect(GRID_HORIZONTAL_OFFSET,GRID_VERTICAL_OFFSET,GRID_WIDTH*CELL_SIZE,GRID_HEIGHT*CELL_SIZE))
    for y in range(GRID_HEIGHT):
        for x in range(GRID_WIDTH):
            if game_board[y][x]: pygame.draw.rect(screen, BROWN, [x * CELL_SIZE + GRID_HORIZONTAL_OFFSET, (y ) * CELL_SIZE + GRID_VERTICAL_OFFSET, CELL_SIZE, CELL_SIZE],0,3)

    ## Draw the player
    if running or score==0:
        if direction == -1: pygame.draw.circle(screen,(255,255,0),(player_x * CELL_SIZE + GRID_HORIZONTAL_OFFSET + 9, player_y * CELL_SIZE + GRID_VERTICAL_OFFSET + 26),6,0)
        sprite_at(screen, player_x * CELL_SIZE + GRID_HORIZONTAL_OFFSET - 6, player_y * CELL_SIZE + GRID_VERTICAL_OFFSET - 6, 'astronaut', SPRITE_SIZE)
    else: 
        sprite_at(screen, player_x * CELL_SIZE + GRID_HORIZONTAL_OFFSET - 22, player_y * CELL_SIZE+ GRID_VERTICAL_OFFSET - 20, 'skull', SPRITE_SIZE * 2)
        display_high_scores(screen, high_score_table(0), GRID_WIDTH * CELL_SIZE + (GRID_HORIZONTAL_OFFSET * 5), 380, 90, 20, with_date = False)

    ## The game has not started or the player has died
    if not running:
        print_at(screen, 500, 300, f' SCORE: {score} ', 32)
        print_at(screen, 440, 150, status, 24)
        if(score>0): print_at(screen, 430, 200, notice, 24)
        pygame.display.update()
        continue

    ## Is it fall time?
    if cycles // fall_cycles_per_tick == cycles / fall_cycles_per_tick:
        ## The player will fall if there's no ground below them
        if direction == 1:
            if game_board[player_y + 1][player_x] == 0:
                if player_y > SCROLL_LIMIT: scroll_up()
                else: player_y += 1
                score += 1
                death_timer = (death_timer // 2)
        else:
            ## The player is flying.
            if game_board[player_y - 1][player_x] == 0 and player_y > 0 and jet_fuel > 0:
                player_y -= 1
                jet_fuel -= 1
                score -= score // 100
                death_timer = (death_timer // 2)
            else:
                ## The player hit their head, flew too high or ran out of fuel so now they will fall
                direction = 1
                crunch_sound.play()

        ## Bombs and loot in mid-air will fall:
        for i in reversed(range(len(bomb_list))):
            bomb_y, bomb_x, timer = bomb_list[i]
            if game_board[bomb_y+1][bomb_x]==0: bomb_list[i] = (bomb_y+1,bomb_x,timer)
        for i in reversed(range(len(loot_list))):
            loot_y, loot_x, loot_type = loot_list[i]
            if loot_y < GRID_HEIGHT - 1 and game_board[loot_y+1][loot_x]==0: loot_list[i] = (loot_y+1,loot_x,loot_type)

    ## Draw loot
    for item in loot_list:
        y,x,t = item 
        if y < GRID_HEIGHT:
            if game_board[y][x]!=0:game_board[y][x]=0
            sprite_at(screen, x * CELL_SIZE + GRID_HORIZONTAL_OFFSET - 7, y * CELL_SIZE + GRID_VERTICAL_OFFSET - 6, f"{loot_table[t]}", SPRITE_SIZE)

    ## Test for player collision
    for i, tup in enumerate(loot_list):
        if tup[0] == player_y and tup[1] == player_x:
            loot_type = tup[2]
            loot_list.pop(i)
            if loot_type == 4: 
                shields-= 1
                if shields < 0: boom(player_y, player_x)
            elif loot_type == 3: shields += STARTING_SHIELDS // 2
            elif loot_type == 2: jet_fuel += STARTING_JET_FUEL // 2
            elif loot_type == 1: bombs += STARTING_BOMBS // 2
            else: score += GEM_SCORE
            if loot_type < 4:
                bling_sound.play()
            else: spark_sound.play() 

    ## Draw bombs and burn fuses
    for i in reversed(range(len(bomb_list))):
        bomb_y, bomb_x, timer = bomb_list[i]
        sprite_at(screen, bomb_x * CELL_SIZE + GRID_HORIZONTAL_OFFSET - 4, bomb_y * CELL_SIZE + GRID_VERTICAL_OFFSET - 6,'bomb', SPRITE_SIZE)
        print_at(screen, bomb_x * CELL_SIZE + GRID_HORIZONTAL_OFFSET + 6, bomb_y * CELL_SIZE + GRID_VERTICAL_OFFSET + 5, f"{timer}", 9)
        if cycles % BOMB_CYCLES_PER_TICK == 0:
            bomb_list[i] = (bomb_y, bomb_x, timer - 1)
            if timer == 1:
                bomb_list.pop(i)
                boom(bomb_y, bomb_x)

    ## Test for death timeout
    if death_timer == DEATH_TIMEOUT:
        shields = 0
        boom(player_y,player_x)

    ## Display game information
    print_at(screen, 500, 50, f' JET FUEL: {jet_fuel} ', 32)
    if(shields>0):print_at(screen, 500, 100, f' SHIELDS: {shields} ', 32)
    if(bombs>0): print_at(screen, 500, 150, f' BOMBS: {bombs} ', 32)
    print_at(screen, 500, 300, f' SCORE: {score} ', 32)
    if status != '': print_at(screen, 500, 150, status, 32)
    print_at(screen, GRID_HORIZONTAL_OFFSET, (GRID_HEIGHT*CELL_SIZE)+(GRID_VERTICAL_OFFSET + 8), f'g:{(fall_cycles_per_tick * 2 - 0.02):.2f} m/s\u00B2 Difficulty: {DIFF_STRING[DIFFICULTY-1]}', 22)
    x,y = WINDOW_SIZE
    print_at(screen, x-192, (GRID_HEIGHT*CELL_SIZE)+(GRID_VERTICAL_OFFSET + 8), ' <ESC> to quit ', 22)

    draw_death_clock(screen, GRID_WIDTH * CELL_SIZE + GRID_HORIZONTAL_OFFSET + 50, GRID_VERTICAL_OFFSET + 16 , 16, death_timer, DEATH_TIMEOUT)

    ## Add a tick and continue
    cycles += 1
    death_timer += 1
    pygame.display.update()
    clock.tick(FPS)

pygame.mixer.quit()
pygame.quit()
