"""Rasterize the saved network layout for portable Word/PDF documents."""
from io import BytesIO
from math import atan2, cos, sin, hypot, sqrt
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .engine import active
from .report_text import RELATIONS, hu


def graph_positions(data):
    positions = {p.id: (150, 140+i*110) for i, p in enumerate(data.persons)}
    positions.update({c.id: (490+(i % 2)*340, 140+(i//2)*125) for i, c in enumerate(data.companies)})
    positions.update({key: (p.x, p.y) for key, p in data.graph_positions.items()})
    return positions


def graph_image(data, calculation, year):
    positions = graph_positions(data)
    width = max(1030, max(x for x, y in positions.values())+140)
    height = max(470, max(y for x, y in positions.values())+115)
    scale = min(2, 2800/max(width, height), sqrt(12000000/(width*height)))
    image = Image.new('RGB', (round(width*scale), round(height*scale)), '#F8FAF5')
    draw = ImageDraw.Draw(image)
    fonts = {}

    def font(size, bold=False):
        key = size, bold
        if key not in fonts:
            name = 'DejaVuSans-Bold.ttf' if bold else 'DejaVuSans.ttf'
            path = Path('/usr/share/fonts/truetype/dejavu') / name
            fonts[key] = ImageFont.truetype(str(path), max(1, round(size*scale))) if path.exists() else ImageFont.load_default(size=max(1, round(size*scale)))
        return fonts[key]

    def text(x, y, value, size=11, fill='#294E40', bold=False, center=False):
        draw.text((x*scale, y*scale), str(value), font=font(size, bold), fill=fill, anchor='mm' if center else 'la')

    def box(bounds, fill, outline=None, radius=10):
        draw.rounded_rectangle(tuple(v*scale for v in bounds), radius=round(radius*scale), fill=fill, outline=outline, width=max(1, round(scale*1.5)))

    root = next(c for c in data.companies if c.id == data.root)
    result = next(y for y in calculation['years'] if y['year'] == year)
    root_fin = next((f for f in data.financials if f.company == data.root and f.year == year), None)
    from datetime import date
    day = data.as_of if data.structure_basis == 'assessment' or (root_fin and root_fin.estimated and root_fin.end and root_fin.end > data.as_of) else date.fromisoformat(result['closing'])
    rows = {r['company']: r for r in result['rows']}
    colors = {'own': '#234B3F', 'linked': '#477A52', 'partner': '#A47A26', 'independent': '#859080', 'unresolved': '#AD6246', 'consolidated': '#477A52'}
    text(24, 24, f'{root.name} · Cégháló', 18, bold=True)
    text(24, 51, f'{year} · Hálóidőpont: {day.isoformat()}'+(' · Előzetes minősítés' if calculation['blockers'] else ''), 11, '#65765E')

    def boundary(a, b):
        dx, dy = b[0]-a[0], b[1]-a[1]
        ratio = 1/max(abs(dx)/105, abs(dy)/36, 1)
        return a[0]+dx*ratio, a[1]+dy*ratio

    def edge(first, second, label, color, dashed=False, arrow=False):
        if first not in positions or second not in positions:
            return
        a, b = boundary(positions[first], positions[second]), boundary(positions[second], positions[first])
        length = hypot(b[0]-a[0], b[1]-a[1])
        if dashed and length:
            for offset in range(0, round(length), 12):
                start, end = offset/length, min(offset+7, length)/length
                draw.line([(scale*(a[0]+(b[0]-a[0])*t), scale*(a[1]+(b[1]-a[1])*t)) for t in [start, end]], fill=color, width=max(1, round(2*scale)))
        else:
            draw.line([(x*scale, y*scale) for x, y in [a, b]], fill=color, width=max(1, round(2*scale)))
        if arrow and length:
            angle = atan2(b[1]-a[1], b[0]-a[0])
            draw.polygon([(b[0]*scale, b[1]*scale), ((b[0]-9*cos(angle-.45))*scale, (b[1]-9*sin(angle-.45))*scale), ((b[0]-9*cos(angle+.45))*scale, (b[1]-9*sin(angle+.45))*scale)], fill=color)
        x, y = (a[0]+b[0])/2, (a[1]+b[1])/2
        label_width = max(90, draw.textlength(label, font=font(10))/scale+12)
        box((x-label_width/2, y-22, x+label_width/2, y-2), '#FFFFFF', radius=5)
        text(x, y-12, label, 10, color, center=True)

    for o in data.ownerships:
        if active(o, day):
            edge(o.owner, o.company, f'{hu(o.capital)}% tőke · {hu(o.votes)}% szavazat'+(' · irányítás' if o.control else ''), '#698477', arrow=True)
    for d in data.decisions:
        if active(d, day):
            edge(d.first, d.second, RELATIONS[d.relation]+(' '+hu(d.percent)+'%' if d.relation == 'partner' else '')+(' · ?' if not d.confirmed else ''), colors.get(d.relation, '#AD6246'), dashed=True)
    for f in data.families:
        edge(f.first, f.second, f.relationship, '#8D779D', dashed=True)
    for actor in [*data.persons, *data.companies]:
        x, y = positions[actor.id]
        row = rows.get(actor.id)
        person = actor in data.persons
        own = actor.id == data.root
        color = colors.get(row['relation'], '#859080') if row else '#859080'
        box((x-105, y-36, x+105, y+36), '#234B3F' if own else '#EDF2E6' if person else '#FFFFFF', color)
        words, lines, line = actor.name.split(), [], ''
        for word in words:
            trial = (line+' '+word).strip()
            if line and draw.textlength(trial, font=font(12, True)) > 190*scale:
                lines.append(line); line = word
            else:
                line = trial
        lines.append(line)
        shown = lines[:2]
        if len(lines) > 2:
            shown[-1] = shown[-1][:24]+'…'
        for i, name in enumerate(shown):
            text(x, y-13+i*15 if len(shown) > 1 else y-6, name, 12, '#FFFFFF' if own else '#294E40', True, True)
        state = 'Természetes személy' if person else ('Közjogi szereplő' if actor.kind == 'public' else RELATIONS[row['relation']].replace(' vállalkozás', '')+' · '+hu(row['percent'])+'%' if row else 'Az adott időpontban nem aktív')
        text(x, y+23, state, 9, '#DEEBBF' if own else color, center=True)
    text(24, height-29, 'Nyíl: tulajdon/szavazat · Szaggatott: döntés vagy rokonság · A rokonság önmagában nem jelent kapcsolódást.', 10, '#65765E')
    output = BytesIO(); image.save(output, format='PNG'); output.seek(0)
    return output
