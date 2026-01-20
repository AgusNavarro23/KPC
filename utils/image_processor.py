from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps
import io
import os
import math

class PhotocardProcessor:
    def __init__(self):
        self.photo_width = 600
        self.photo_height = 900
        
        self.border_size = 50      # Marco un poco más ancho para la textura
        self.info_height = 280     # Espacio inferior
        self.corner_radius = 40    # Redondeo de la foto
        
        # Colores: (Color Principal, Color Secundario para degradado)
        self.rarity_theme = {
            'Common':    ('#B0BEC5', '#78909C'),  # Plata / Gris
            'Uncommon':  ('#66BB6A', '#2E7D32'),  # Verde Bosque
            'Rare':      ('#42A5F5', '#1565C0'),  # Azul Océano
            'Epic':      ('#AB47BC', '#6A1B9A'),  # Púrpura Místico
            'Legendary': ('#FFCA28', '#FF6F00')   # Oro / Naranja Fuego
        }
        
        self.font_path = self._get_font_path()
        
        # Compatibilidad con versiones antiguas de Pillow
        self.resample_method = Image.Resampling.LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS
    
    def _get_font_path(self):
        """Intenta cargar una fuente personalizada primero"""
        possible_fonts = [
            'data/fonts/font.ttf', 
            'data/fonts/arialbd.ttf', # Windows Bold
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
            'C:\\Windows\\Fonts\\Arial.ttf'
        ]
        for font in possible_fonts:
            if os.path.exists(font):
                return font
        return None
    
    def create_photocard(self, image_path, card_data):
        rarity = card_data.get('rarity', 'Common')
        colors = self.rarity_theme.get(rarity, ('#555555', '#333333'))
        
        # 1. Dimensiones
        total_width = self.photo_width + (self.border_size * 2)
        total_height = self.photo_height + self.border_size + self.info_height
        
        # 2. Crear Fondo con Degradado y Textura
        canvas = self._create_textured_background(total_width, total_height, colors[0], colors[1])
        draw = ImageDraw.Draw(canvas)
        
        # 3. Procesar Imagen del Idol (Recorte + Redondeo)
        try:
            img = Image.open(image_path).convert("RGBA")
            # Crop to fill
            img_ratio = img.width / img.height
            target_ratio = self.photo_width / self.photo_height
            
            if img_ratio > target_ratio:
                new_width = int(self.photo_height * img_ratio)
                img = img.resize((new_width, self.photo_height), self.resample_method)
                left = (new_width - self.photo_width) // 2
                img = img.crop((left, 0, left + self.photo_width, self.photo_height))
            else:
                new_height = int(self.photo_width / img_ratio)
                img = img.resize((self.photo_width, new_height), self.resample_method)
                top = (new_height - self.photo_height) // 2
                img = img.crop((0, top, self.photo_width, top + self.photo_height))
            
            # Redondear esquinas de la foto
            img = self._round_corners(img, self.corner_radius)
            
        except Exception as e:
            print(f"Error imagen: {e}")
            # Fondo blanco si falla la imagen
            img = Image.new('RGBA', (self.photo_width, self.photo_height), 'white')
            img = self._round_corners(img, self.corner_radius)

        # 4. Pegar Imagen (con sombra detrás para profundidad)
        photo_x = self.border_size
        photo_y = self.border_size
        
        # Sombra de la foto
        shadow = Image.new('RGBA', (self.photo_width, self.photo_height), (0,0,0,0))
        shadow_draw = ImageDraw.Draw(shadow)
        # Ajuste para evitar error de coordenadas en Pillow viejos
        shadow_draw.rounded_rectangle([(0,0), (self.photo_width-1, self.photo_height-1)], radius=self.corner_radius, fill=(0,0,0,80))
        canvas.paste(shadow, (photo_x + 10, photo_y + 10), shadow)
        
        # Foto real
        canvas.paste(img, (photo_x, photo_y), img)
        
        # 5. Textos e Información
        self._draw_stylish_text(canvas, draw, card_data, total_width, total_height, colors[1])
        
        # 6. Overlay Brillante (Holográfico simple)
        if rarity in ['Epic', 'Legendary']:
            self._add_shine_overlay(canvas)

        # Output
        img_bytes = io.BytesIO()
        canvas.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        return img_bytes

    def _create_textured_background(self, w, h, color_start, color_end):
        """Crea un degradado vertical y añade líneas de textura"""
        base = Image.new('RGB', (w, h), color_start)
        draw = ImageDraw.Draw(base)
        
        r1, g1, b1 = self._hex_to_rgb(color_start)
        r2, g2, b2 = self._hex_to_rgb(color_end)
        
        for y in range(h):
            r = int(r1 + (r2 - r1) * y / h)
            g = int(g1 + (g2 - g1) * y / h)
            b = int(b1 + (b2 - b1) * y / h)
            draw.line([(0, y), (w, y)], fill=(r,g,b))
            
        # Textura
        texture = Image.new('RGBA', (w, h), (0,0,0,0))
        txt_draw = ImageDraw.Draw(texture)
        
        step = 10 
        for i in range(-h, w, step):
            txt_draw.line([(i, 0), (i + h, h)], fill=(0,0,0,20), width=1)
            txt_draw.line([(i+1, 0), (i + h + 1, h)], fill=(255,255,255,10), width=1)
            
        base.paste(texture, (0,0), texture)
        return base

    def _round_corners(self, img, radius):
        mask = Image.new("L", img.size, 0)
        draw = ImageDraw.Draw(mask)
        draw.rounded_rectangle([(0, 0), (img.width-1, img.height-1)], radius=radius, fill=255)
        out = ImageOps.fit(img, mask.size, centering=(0.5, 0.5))
        out.putalpha(mask)
        return out

    def _draw_stylish_text(self, canvas, draw, data, w, h, accent_color):
        member = data.get('member', 'Unknown').upper()
        group = data.get('group', 'Unknown').upper()
        
        try:
            if self.font_path:
                font_giant = ImageFont.truetype(self.font_path, 85)
                font_large = ImageFont.truetype(self.font_path, 45)
                font_small = ImageFont.truetype(self.font_path, 24)
            else:
                font_giant = ImageFont.load_default()
                font_large = font_small = ImageFont.load_default()
        except:
            font_giant = font_large = font_small = ImageFont.load_default()

        text_area_start = self.photo_height + self.border_size
        center_x = w // 2
        
        # Nombre
        name_y = text_area_start + 40
        self._draw_text_with_outline(draw, center_x, name_y, member, font_giant, 'white', 3)
        
        # Grupo
        group_y = name_y + 85
        if hasattr(draw, 'textbbox'):
            group_bbox = draw.textbbox((0,0), f"  {group}  ", font=font_large)
            gw = group_bbox[2] - group_bbox[0]
            gh = group_bbox[3] - group_bbox[1]
        else:
            gw, gh = 200, 50

        draw.rounded_rectangle(
            [center_x - gw//2, group_y, center_x + gw//2, group_y + gh + 10], 
            radius=10, fill=(0,0,0,60)
        )
        self._draw_text_with_outline(draw, center_x, group_y, group, font_large, '#EEEEEE', 1)

        # Etiqueta Superior
        serial = data.get('serial')
        series = data.get('series', 'S1')
        card_num = data.get('card_number', '000')
        
        if serial:
            tag_text = f"PRINT #{serial.split('-')[-1][-4:]}"
        else:
            tag_text = f"{series} · {card_num}"
            
        draw.polygon([(20, 0), (20, 60), (160, 60), (180, 0)], fill=accent_color)
        draw.text((40, 15), tag_text, font=font_small, fill='white')

        # Rareza
        rarity = data.get('rarity', 'Common').upper()
        rx = w - 40
        ry = h - 40
        
        if hasattr(draw, 'textbbox'):
            bbox = draw.textbbox((0,0), rarity, font=font_small)
            tw = bbox[2] - bbox[0]
        else:
            tw = 100

        draw.text((rx - tw, ry - 20), rarity, font=font_small, fill='white')
        draw.line([(rx - tw - 10, ry + 10), (rx, ry + 10)], fill='white', width=2)

    def _draw_text_with_outline(self, draw, x, y, text, font, fill_color, outline_width):
        if hasattr(draw, 'textbbox'):
            bbox = draw.textbbox((0, 0), text, font=font)
            text_width = bbox[2] - bbox[0]
        else:
            text_width = 0
            
        start_x = x - (text_width // 2)
        
        shadow_color = 'black'
        for off_x in range(-outline_width, outline_width + 1):
            for off_y in range(-outline_width, outline_width + 1):
                draw.text((start_x + off_x, y + off_y), text, font=font, fill=shadow_color)
        
        draw.text((start_x, y), text, font=font, fill=fill_color)

    def _add_shine_overlay(self, canvas):
        overlay = Image.new('RGBA', canvas.size, (0,0,0,0))
        draw = ImageDraw.Draw(overlay)
        w, h = canvas.size
        draw.polygon([(0, h), (150, h), (w, 0), (w-150, 0)], fill=(255, 255, 255, 30))
        canvas.paste(overlay, (0,0), overlay)

    def _hex_to_rgb(self, hex_color):
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

    # --- FUNCIÓN AGREGADA QUE FALTABA ---
    def create_card_grid(self, card_images, cols=3):
        """Crea una cuadrícula con las imágenes de las cartas para el drop"""
        if not card_images:
            return None
        
        # Filtrar Nones por si acaso alguna imagen falló totalmente
        valid_images = [img for img in card_images if img is not None]
        if not valid_images:
            return None

        rows = (len(valid_images) + cols - 1) // cols
        
        try:
            # Abrir la primera imagen para obtener dimensiones base
            sample = Image.open(valid_images[0])
            w, h = sample.size
        except Exception as e:
            print(f"Error grid sample: {e}")
            return None
            
        # Espacio entre cartas
        padding = 40
        
        grid_w = cols * w + (cols + 1) * padding
        grid_h = rows * h + (rows + 1) * padding
        
        # Fondo oscuro para el grid
        grid = Image.new('RGB', (grid_w, grid_h), '#121212')
        
        for idx, img_bytes in enumerate(valid_images):
            try:
                img = Image.open(img_bytes)
                row = idx // cols
                col = idx % cols
                
                x = padding + col * (w + padding)
                y = padding + row * (h + padding)
                
                grid.paste(img, (x, y))
            except Exception as e:
                print(f"Error pegando en grid: {e}")
                continue
            
        grid_bytes = io.BytesIO()
        grid.save(grid_bytes, format='PNG')
        grid_bytes.seek(0)
        return grid_bytes