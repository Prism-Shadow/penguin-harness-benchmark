import copy
import random


RENDER_NODES = (829, 830, 831, 832, 833, 834, 839, 848, 849, 851, 852, 853, 854, 855, 858, 859, 860, 861)


def fixture(seed, video=False, loop=False):
    randomizer = random.Random(seed)
    colors = []
    for channel in range(3):
        color = [randomizer.randrange(20, 60) for _ in range(3)]
        color[channel] = randomizer.randrange(190, 240)
        colors.append(color)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="2600" height="300">'
    svg += '<rect width="2600" height="300" fill="white"/>'
    frames = []
    for index, color in enumerate(colors):
        svg += f'<rect x="{index * 1000}" y="0" width="400" height="300" fill="rgb{tuple(color)}"/>'
        frames.append({
            'frameId': f'frame-{seed}-{index}', 'title': f'Frame {index + 1}',
            'showFrameNumber': False, 'showInFrameList': False,
            'timeoutEnable': index < 2 or loop, 'timeoutMs': 500,
            'transitionDurationMs': 1500 if video else 6000,
            'layerProperties': {'__sozi_auto__': {'transitionTimingFunction': 'linear'}},
            'cameraStates': {'__sozi_auto__': {
                'cx': index * 1000 + 200, 'cy': 150, 'width': 400, 'height': 300,
                'angle': 0, 'opacity': 1, 'clipped': False,
            }},
        })
    return {'svg': svg + '</svg>', 'colors': colors, 'presentation': {
        'aspectWidth': 4, 'aspectHeight': 3, 'frames': frames,
        'elementsToHide': [], 'customFiles': [], 'updateURLOnFrameChange': True,
    }}


def cases():
    result = []
    for index, (page, orientation, include, exclude, selected) in enumerate([
        ('A4', 'landscape', '1:3', '2', [0, 2]),
        ('Letter', 'portrait', '2,3', '3', [1]),
        ('A5', 'portrait', '1:3', '2', [0, 2]),
        ('Tabloid', 'portrait', '1', '', [0]),
        ('A3', 'landscape', '3,1', '', [0, 2]),
        ('Legal', 'landscape', '2', '', [1]),
    ]):
        result.append(dict(fixture(70 + index), name=f'pdf-{page}-{orientation}', format='pdf',
                           command='exportToPDF', output='deck.sozi.pdf', selected=selected,
                           nodes=[829, 830, 831, 832, 833, 834], options={
            'exportToPDFPageSize': page, 'exportToPDFPageOrientation': orientation,
            'exportToPDFInclude': include, 'exportToPDFExclude': exclude,
        }))
    for index, size in enumerate(['screen16x9', 'screen4x3']):
        result.append(dict(fixture(80 + index), name=f'pptx-{size}', format='pptx',
                           command='exportToPPTX', output='deck.sozi.pptx', selected=[0, 2],
                           nodes=[848, 849, 851, 852], options={
            'exportToPPTXSlideSize': size, 'exportToPPTXInclude': '1:3', 'exportToPPTXExclude': '2',
        }))
    for index, (container, width, height, loop) in enumerate([
        ('png', 320, 180, False), ('png', 256, 192, True), ('webm', 320, 180, False),
    ]):
        result.append(dict(fixture(90 + index, video=True, loop=loop), name=f'{container}-{width}',
                           format=container, command='exportToVideo',
                           output='deck-sozi-export' if container == 'png' else 'deck.sozi.webm',
                           loop=loop, nodes=[853, 854, 855, 860] if container == 'png' else [853, 854, 855, 859, 861],
                           options={'exportToVideoFormat': container, 'exportToVideoWidth': width,
                                    'exportToVideoHeight': height, 'exportToVideoFrameRate': 4,
                                    'exportToVideoBitRate': 1000000}))
    encoded = result[-1]
    result.append(dict(next(c for c in result if c['format'] == 'png'), name='png-plain-html', htmlName='deck.html'))
    result.append(dict(encoded, name='webm-fallback', fallback=True, nodes=[858, 859]))
    result.append(dict(encoded, name='webm-256-fps2', options=dict(encoded['options'],
        exportToVideoWidth=256, exportToVideoHeight=144, exportToVideoFrameRate=2, exportToVideoBitRate=750000)))
    for template in [result[0], next(c for c in result if c['format'] == 'pptx'), next(c for c in result if c['format'] == 'png'), encoded]:
        for fault in ['load', 'capture', 'write'] + (['encoder'] if template['format'] == 'webm' else []):
            result.append(dict(template, name=template['format'] + '-fault-' + fault,
                               fault=fault, nodes=sorted(set(template['nodes'] + [855]))))
    for mode, page in [('only', 'Letter'), ('conflict', 'A5')]:
        template = result[1]
        result.append(dict(template, name='pdf-legacy-' + mode, legacy=mode,
                           options=dict(template['options'], exportToPDFPageSize=page)))
    for container in ['pdf', 'pptx']:
        template = next(c for c in result if c['format'] == container)
        prefix = 'exportToPDF' if container == 'pdf' else 'exportToPPTX'
        for mode in ['none', 'exclude-all']:
            result.append(dict(template, name=container + '-empty-' + mode, expectedFailure=True,
                selected=[], options=dict(template['options'], **{
                    prefix + 'Include': 'none' if mode == 'none' else 'all',
                    prefix + 'Exclude': '' if mode == 'none' else 'all'})))
    for case in result:
        case['options']['exportType'] = 'video' if case['command'] == 'exportToVideo' else case['format']
    for container in ['pdf', 'pptx']:
        case = copy.deepcopy(next(c for c in result if c['format'] == container))
        case.update(name=container + '-hidden-layer', nodes=[851], checkVisibility=True)
        # A real imported SVG layer starts hidden, while its frame camera has
        # positive opacity. Capture must restore it without changing frame state.
        case['svg'] = case['svg'].replace('><rect', '><g id="capture-layer" style="display:none"><rect', 1)
        case['svg'] = case['svg'].replace('</svg>',
            '<rect id="capture-hidden-marker" width="2600" height="300" fill="black"/></g></svg>')
        case['presentation']['elementsToHide'] = ['capture-hidden-marker']
        for frame in case['presentation']['frames']:
            for field in ['layerProperties', 'cameraStates']:
                frame[field]['capture-layer'] = frame[field].pop('__sozi_auto__')
        result.append(case)
    result.append(dict(fixture(174), name='ui-export', format='ui', nodes=[839], options={}))
    return result
