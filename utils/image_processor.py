from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import os

class PhotocardProcessor:
    def __init__(self):
        # Dimensiones estándar de photocard
        self.card_width = 600
        self.card_height = 900
        self.frame_width = 20
        
        # Colores de marcos por rareza
        self.frame_colors = {
            'Common': '#B0B0B0',      # Gris plateado
            'Uncommon': '#4CAF50',    # Verde
            'Rare': '#2196F3',        # Azul
            'Epic': '#9C27B0',        # Púrpura
            'Legendary': '#FFD700'    # Dorado
        }
        
        # Colores de brillo/efectos por rareza
        self.glow_colors = {
            'Common': None,
            'Uncommon': '#81C784',
            'Rare': '#64B5F6',
            'Epic': '#BA68C8',
            'Legendary': '#FFE082'
        }
        
        # Intentar cargar fuentes (usa fuentes del sistema si están disponibles)
        self.font_path = self._get_font_path()
    
    def _get_font_path(self):
        """Intenta encontrar una fuente disponible en el sistema"""
        possible_fonts = [
            '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',  # Linux
            'C:\\Windows\\Fonts\\Arial.ttf',  # Windows
            '/System/Library/Fonts/Helvetica.ttc',  # macOS
            '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'  # Linux alternativo
        ]
        
        for font in possible_fonts:
            if os.path.exists(font):
                return font
        
        return None  # Usará fuente por defecto
    
    def create_photocard(self, image_path, card_data):
        """
        Crea una photocard con marco y efectos según la rareza
        
        Args:
            image_path: Ruta a la imagen original
            card_data: dict con 'rarity', 'card_number', 'member', 'group', 'era'
        
        Returns:
            BytesIO object con la imagen procesada
        """
        rarity = card_data.get('rarity', 'Common')
        card_number = card_data.get('card_number', '#000')
        member = card_data.get('member', 'Unknown')
        group = card_data.get('group', 'Unknown')
        era = card_data.get('era', '')
        series = card_data.get('series', 'S1')
        
        # Crear canvas base
        canvas_width = self.card_width + (self.frame_width * 2)
        canvas_height = self.card_height + (self.frame_width * 2) + 120  # Espacio para info
        
        canvas = Image.new('RGB', (canvas_width, canvas_height), 'white')
        draw = ImageDraw.Draw(canvas)
        
        # Cargar imagen original o crear placeholder
        try:
            img = Image.open(image_path)
            img = img.resize((self.card_width, self.card_height), Image.Resampling.LANCZOS)
        except:
            # Crear placeholder si no existe la imagen
            img = self._create_placeholder(member, group)
        
        # Crear marco con efecto según rareza
        self._draw_frame(canvas, draw, rarity)
        
        # Pegar imagen en el centro
        canvas.paste(img, (self.frame_width, self.frame_width))
        
        # Agregar información de la carta
        self._add_card_info(canvas, draw, card_number, member, group, era, series, rarity)
        
        # Agregar efectos especiales para rarezas altas
        if rarity in ['Epic', 'Legendary']:
            canvas = self._add_special_effects(canvas, rarity)
        
        # Convertir a bytes
        img_bytes = io.BytesIO()
        canvas.save(img_bytes, format='PNG', quality=95)
        img_bytes.seek(0)
        
        return img_bytes
    
    def _draw_frame(self, canvas, draw, rarity):
        """Dibuja el marco de la photocard"""
        frame_color = self.frame_colors.get(rarity, self.frame_colors['Common'])
        
        # Marco exterior (más grueso para rarezas altas)
        thickness = self.frame_width
        if rarity == 'Legendary':
            thickness = self.frame_width + 5
        elif rarity == 'Epic':
            thickness = self.frame_width + 3
        
        # Dibujar marco principal
        for i in range(thickness):
            draw.rectangle(
                [i, i, canvas.width - i - 1, self.card_height + self.frame_width + i],
                outline=frame_color,
                width=2
            )
        
        # Marco interior (más sutil)
        inner_color = self._adjust_brightness(frame_color, 1.3)
        draw.rectangle(
            [thickness - 3, thickness - 3, 
             canvas.width - thickness + 3, self.card_height + thickness + 3],
            outline=inner_color,
            width=1
        )
    
    def _add_card_info(self, canvas, draw, card_number, member, group, era, series, rarity):
        """Agrega la información de la carta en la parte inferior"""
        info_y = self.card_height + self.frame_width * 2 + 10
        
        # Cargar fuentes
        try:
            if self.font_path:
                font_large = ImageFont.truetype(self.font_path, 32)
                font_medium = ImageFont.truetype(self.font_path, 24)
                font_small = ImageFont.truetype(self.font_path, 18)
            else:
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
        except:
            font_large = ImageFont.load_default()
            font_medium = ImageFont.load_default()
            font_small = ImageFont.load_default()
        
        frame_color = self.frame_colors.get(rarity, self.frame_colors['Common'])
        
        # Número de carta (esquina superior izquierda del marco)
        draw.text((25, 15), f"{series}-{card_number}", fill=frame_color, font=font_small)
        
        # Nombre del miembro (centrado)
        member_text = member.upper()
        bbox = draw.textbbox((0, 0), member_text, font=font_large)
        text_width = bbox[2] - bbox[0]
        text_x = (canvas.width - text_width) // 2
        draw.text((text_x, info_y), member_text, fill='black', font=font_large)
        
        # Grupo
        group_text = group
        bbox = draw.textbbox((0, 0), group_text, font=font_medium)
        text_width = bbox[2] - bbox[0]
        text_x = (canvas.width - text_width) // 2
        draw.text((text_x, info_y + 40), group_text, fill='#555555', font=font_medium)
        
        # Era (si existe)
        if era:
            era_text = f"Era: {era}"
            bbox = draw.textbbox((0, 0), era_text, font=font_small)
            text_width = bbox[2] - bbox[0]
            text_x = (canvas.width - text_width) // 2
            draw.text((text_x, info_y + 75), era_text, fill='#888888', font=font_small)
        
        # Rareza (esquina inferior derecha)
        rarity_text = rarity.upper()
        bbox = draw.textbbox((0, 0), rarity_text, font=font_small)
        text_width = bbox[2] - bbox[0]
        draw.text((canvas.width - text_width - 25, canvas.height - 25), 
                  rarity_text, fill=frame_color, font=font_small)
    
    def _add_special_effects(self, canvas, rarity):
        """Agrega efectos especiales para cartas Epic y Legendary"""
        if rarity == 'Legendary':
            # Efecto de brillo dorado
            overlay = Image.new('RGBA', canvas.size, (255, 215, 0, 0))
            draw = ImageDraw.Draw(overlay)
            
            # Dibujar líneas de brillo en las esquinas
            glow_color = (255, 215, 0, 80)
            for i in range(0, 40, 4):
                draw.line([(i, 0), (0, i)], fill=glow_color, width=2)
                draw.line([(canvas.width - i, 0), (canvas.width, i)], fill=glow_color, width=2)
            
            # Combinar con la imagen original
            canvas = canvas.convert('RGBA')
            canvas = Image.alpha_composite(canvas, overlay)
            canvas = canvas.convert('RGB')
        
        elif rarity == 'Epic':
            # Efecto de brillo púrpura más sutil
            overlay = Image.new('RGBA', canvas.size, (156, 39, 176, 0))
            draw = ImageDraw.Draw(overlay)
            
            glow_color = (156, 39, 176, 60)
            for i in range(0, 30, 5):
                draw.line([(i, 0), (0, i)], fill=glow_color, width=2)
                draw.line([(canvas.width - i, 0), (canvas.width, i)], fill=glow_color, width=2)
            
            canvas = canvas.convert('RGBA')
            canvas = Image.alpha_composite(canvas, overlay)
            canvas = canvas.convert('RGB')
        
        return canvas
    
    def _create_placeholder(self, member, group):
        """Crea una imagen placeholder cuando no existe la imagen original"""
        img = Image.new('RGB', (self.card_width, self.card_height), '#E0E0E0')
        draw = ImageDraw.Draw(img)
        
        # Intentar cargar fuente
        try:
            if self.font_path:
                font = ImageFont.truetype(self.font_path, 48)
            else:
                font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Dibujar texto centrado
        text = f"{member}\n{group}"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (self.card_width - text_width) // 2
        y = (self.card_height - text_height) // 2
        
        draw.text((x, y), text, fill='#757575', font=font, align='center')
        
        return img
    
    def _adjust_brightness(self, hex_color, factor):
        """Ajusta el brillo de un color hexadecimal"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        r = min(255, int(r * factor))
        g = min(255, int(g * factor))
        b = min(255, int(b * factor))
        
        return f'#{r:02x}{g:02x}{b:02x}'
    
    def create_card_grid(self, card_images, cols=3):
        """Crea una cuadrícula de múltiples photocards"""
        if not card_images:
            return None
        
        # Calcular dimensiones
        rows = (len(card_images) + cols - 1) // cols
        grid_width = cols * (self.card_width + self.frame_width * 2) + (cols - 1) * 20
        grid_height = rows * (self.card_height + self.frame_width * 2 + 120) + (rows - 1) * 20
        
        # Crear canvas
        grid = Image.new('RGB', (grid_width, grid_height), 'white')
        
        # Pegar imágenes
        for idx, img_bytes in enumerate(card_images):
            img = Image.open(img_bytes)
            row = idx // cols
            col = idx % cols
            
            x = col * (self.card_width + self.frame_width * 2 + 20)
            y = row * (self.card_height + self.frame_width * 2 + 120 + 20)
            
            grid.paste(img, (x, y))
        
        # Convertir a bytes
        grid_bytes = io.BytesIO()
        grid.save(grid_bytes, format='PNG', quality=95)
        grid_bytes.seek(0)
        
        return grid_bytes