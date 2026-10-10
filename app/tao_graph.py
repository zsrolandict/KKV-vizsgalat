"""Render the Tao evidence network with the same saved coordinates as the workbench."""
from io import BytesIO
from math import atan2, cos, sin, sqrt
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from .tao_engine import active
from .tao_models import FAMILY_LABELS


def graph_image(data):
    actors = [*data.persons, *data.companies]
    positions = {a.id: (160+(i % 3)*320, 160+(i//3)*160) for i, a in enumerate(actors)}
    positions.update({key: (p.x, p.y) for key, p in data.graph_positions.items()})
    width = max(1020, max(x for x, y in positions.values())+150)
    height = max(550, max(y for x, y in positions.values())+90)
    scale = min(2, 2800/max(width, height), sqrt(12000000/(width*height)))
    image = Image.new('RGB', (round(width*scale), round(height*scale)), '#f8fafc')
    draw = ImageDraw.Draw(image)
    def font(size):
        path = Path(__file__).parent/'static/fonts/DM-Sans.ttf'
        return ImageFont.truetype(str(path), max(1, round(size*scale)))
    def text(x, y, label, size=11, color='#1c3658', anchor='mm'):
        draw.text((x*scale,y*scale),label,font=font(size),fill=color,anchor=anchor)
    def boundary(a,b):
        dx,dy=b[0]-a[0],b[1]-a[1]
        t=1/max(abs(dx)/120,abs(dy)/38,1)
        return a[0]+dx*t,a[1]+dy*t
    def edge(first,second,label,color='#54778c',arrow=False):
        if first not in positions or second not in positions:return
        a,b=boundary(positions[first],positions[second]),boundary(positions[second],positions[first])
        draw.line([(x*scale,y*scale) for x,y in (a,b)],fill=color,width=max(1,round(2*scale)))
        if arrow:
            angle=atan2(b[1]-a[1],b[0]-a[0])
            draw.polygon([(b[0]*scale,b[1]*scale),*(( (b[0]-10*cos(angle+offset))*scale,(b[1]-10*sin(angle+offset))*scale) for offset in (-.45,.45))],fill=color)
        text((a[0]+b[0])/2,(a[1]+b[1])/2-10,label,10,color)
    text(25,25,f'Tao cégháló · {data.as_of}',18,anchor='la')
    text(25,53,'Rögzített tények; a nyilak nem végleges jogi minősítések.',11,anchor='la')
    for f in data.voting_facts:
        if active(f,data.as_of):
            vote='>50%' if f.vote_mode in ('explicit','expert') and f.vote_bound=='over_half' else str(f.votes)+'%' if f.vote_mode in ('explicit','expert') and f.votes is not None else str(f.capital)+'%*' if f.vote_mode=='ownership_default' and f.capital is not None else '?'
            edge(f.owner,f.company,f'Tőke: {f.capital if f.capital is not None else "?"}% · szavazat: {vote}',arrow=True)
    for f in data.family_facts:
        if active(f,data.as_of):edge(f.first,f.second,FAMILY_LABELS[f.relationship]+('' if f.confirmed else ' · ?'),'#846597')
    for f in data.control_facts:
        if active(f,data.as_of):edge(f.owner,f.company,'Irányítás'+('' if f.confirmed else ' · ?'),'#af7832',True)
    for f in data.management_facts:
        if active(f,data.as_of):edge(f.first,f.second,'Ügyvezetés'+('' if f.confirmed else ' · ?'),'#af7832')
    for f in data.establishment_facts:
        if active(f,data.as_of):edge(f.principal,f.establishment,'Tao-telephely'+('' if f.confirmed else ' · ?'),'#af7832',True)
    for f in data.trust_facts:
        if active(f,data.as_of) and f.asset_entity:
            for owner in f.trustees:edge(owner,f.asset_entity,'BVK · külön vizsgálat','#846597',True)
    for actor in actors:
        x,y=positions[actor.id]
        person=actor in data.persons
        draw.rounded_rectangle(tuple(v*scale for v in (x-120,y-38,x+120,y+38)),radius=round((32 if person else 12)*scale),fill='#eaf3f0' if person else '#ffffff',outline='#1c3658',width=max(1,round(scale)))
        text(x,y-4,actor.name if len(actor.name)<=30 else actor.name[:28]+'…',13)
        text(x,y+19,'Természetes személy' if person else 'Vállalkozás',11,'#536579')
    output=BytesIO();image.save(output,format='PNG');return output.getvalue()
