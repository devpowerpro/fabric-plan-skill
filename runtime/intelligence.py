"""Parameterized Intelligence composition: text, semantic slicers, cards, embeds.

Selected active branches are grounded in exported native state. New generated
instances still require destination readback and separate behavior acceptance.
"""
import copy, html, math
from pathlib import Path
from .construct import field, guid, schema, sheet_properties
from .codec import dumps,load
from .semantic_values import semantic_value

def complete_card_state(props):
    """Fill active KPI store slices, preserving authored labels and layout.

    Supplying a partial store slice can replace frontend defaults. Include
    variance.style even with showVariance=False: theme updates access it.
    """
    from .construct import merge
    from .codec import loads
    defaults=load(Path(__file__).resolve().parents[1]/'fixtures/card-defaults.json')
    p=copy.deepcopy(props);p['chartType']='CARD';vs=p.setdefault('visualState',{})
    vs['chartType']='CARD'
    vs['hiddenProperties_!!!_chartsMode']=dumps({'visualMode':'CARD','prevVisualMode':'CARD','isFromKpiSettings':False}).strip()
    for section in ('kpiControls','numberFormatting'):
        key='hiddenProperties_!!!_'+section;current=vs.get(key,{})
        if isinstance(current,str):current=loads(current)
        value=merge(defaults[section],current)
        if section=='kpiControls':
            for item in value['gridLayout']:
                item.setdefault('fgImage',{'source':'custom','foregroundMeasure':None,'foregroundFill':'contain','customForegroundImage':'','opacity':100})
        vs[key]=dumps(value).strip()
    return p
from .filters import registration, forward_filters
from .layout import overlap, rect

def styles(background='#FFFFFF'):
    return {'background':{'backgroundColor':background,'isEnabled':True},
        'border':{'color':'#DCE5EB','isEnabled':True,'side':'all','width':1},
        'cornerRadius':{'isEnabled':True,'isCustomCornerRadius':False,**{k:8 for k in ('radiusTopLeft','radiusTopRight','radiusBottomLeft','radiusBottomRight')}},
        'padding':{'isEnabled':True,'isCustomPaddingSize':True,'leftPadding':16,'rightPadding':16,'topPadding':10,'bottomPadding':8},
        'shadow':{'isEnabled':False},'rotation':{'isEnabled':False,'transform':0}}

def base(kind, name):
    return {'visualType':kind,'pivotAssignments':[],'superFilterAssignments':[],
            'visualState':{'reportMode':'EDIT'},'layerProperties':{'layerProperties':{'name':name,'groupIds':[],'isHidden':False},'order':0},
            'lockAspectRatio':False,'visualInteractions':{},'visualStyles':styles()}

def page_navigator(direction='horizontal'):
    """Mandatory dashboard navigation, with portable all-visible-page targets."""
    from .navigator_api import state
    p=base(203,'Page Navigator')
    nav=state('PAGE_NAVIGATOR_TABS',palette={'fill':'#EEF1F6','text':'#303C60',
        'activeFill':'#303C60','activeText':'#FFFFFF','border':'#D8DCE5'})
    # Horizontal layout derives the tab count from the live page catalog. Do not
    # persist selectedPages=[] (no tabs), source runtime IDs or generated tabs.
    nav['navigatorTabsState'].update(layoutType=direction,scrollDirection=direction,rows=1,columns=1)
    p['visualState']['navigatorState']=nav
    return p

def slicer(model,spec):
    reg=registration(model,spec); single=reg['configuration']['singleSelect'];required=spec.get('required',False)
    key=spec['field'];label=spec.get('label',reg['pivotAssignments'][0]['name'])
    p=base(60,label);p['pivotAssignments']=copy.deepcopy(reg['pivotAssignments']);p['superFilterAssignments']=[reg]
    vs=p['visualState'];vs.update(slicerFilterAssignments=copy.deepcopy(reg['filter']),
        facetSettings={'facetViewType':'dropdown','facetLayout':'vertical','singleSelect':single,'cascadeFilter':True,
            'enableCategorySearch':True,'showSearchBarIcon':True,'showSelectionState':True,'showFacetHeader':False,
            'displayMode':'label','enableFacetMode':False,'influencedAutoSelect':'none'},
        displaySettings={'fontFamily':'Arial','forcedSelection':required,'displaySelectAll':not required,'hideBlank':True,
            'defaultVisualBackground':'#FFFFFF','selectAllLabel':'Select All','blankLabel':'(Blank)','emptyLabel':'(Empty)'},
        toolbarSettings={'customTitleText':label,'titleLabel':label,'showTitle':True,'titleFontBold':True,
            'titleFontColor':'#36546A','titleFontSize':12,'titleAlignment':'left','titleTextWrap':False,
            'enableSearch':True,'searchDimension':key,'enableClearButton':not required,'showSearchBarIcon':True,
            'showSavedFilter':False,'toolbarType':'fixed','headerHeight':22,'headerBackgroundColor':'#FFFFFF'},
        filterHiddenSettings={'categorySelectAllState':{},'customCategoryLabels':{},'isRegistered':True},
        measureFilterSettings={'enableNumericCategorySlider':'between' in spec,'numericSliderType':'between',
            'numericSliderStep':1,'maxNumericSliderStep':5,'enableNumericSliderFixedLabel':True,
            'numericSliderBold':True,'numericSliderFontSize':10,'showSlider':True,'enableMeasureFilter':False})
    return p

def rich_text(paragraphs, *, name, banner=False):
    """paragraphs: lists of {text, size?, color?, bold?}, serialized as Lexical."""
    children=[]
    for runs in paragraphs:
        nodes=[]
        for r in runs:
            if not isinstance(r['text'],str): raise ValueError('Text content must be string')
            nodes.append({'detail':0,'format':1 if r.get('bold') else 0,'mode':'normal',
                'style':f"font-family: Arial;font-size: {int(r.get('size',13))}px;color: {r.get('color','#36546A')};",
                'text':r['text'],'type':'text','version':1})
        children.append({'children':nodes,'direction':'ltr','format':'','indent':0,'type':'paragraph','version':1,'textFormat':0,'textStyle':''})
    p=base(202,name);p['visualStyles']=styles('#193446' if banner else '#EEF4F6')
    p['visualState']['text']=dumps({'root':{'children':children,'direction':'ltr','format':'','indent':0,'type':'root','version':1}}).strip()
    return p

def card(model,spec,registry, *, query_fields=()):
    if set(spec)-{'field','label','aggregation'}: raise ValueError('Unconsumed card options')
    key=spec['field'];source=next((f for f in model['fields'] if f['id']==key),None)
    if source:
        a=semantic_value(model,key,registry,aggregation=spec.get('aggregation'))
    else:
        matches=[q for q in query_fields if q.get('id')==key]
        if len(matches)!=1: raise ValueError('KPI source absent from current model/query catalog')
        a=copy.deepcopy(matches[0])
        required={'id','sourceId','queryId','tableName','columnName','columnType','dataType','sourceType','measureGuid'}
        if not required<=a.keys() or a['sourceType']!='InfoBridge' or a['dataType'] not in ('Int64','Double','Decimal') or a['sourceId']!=key:
            raise ValueError('Incomplete registered InfoBridge KPI field')
        if spec.get('aggregation') not in ('sum','min','max','count','avg'): raise ValueError('Query KPI requires explicit aggregation')
        a.update(customSource=True,dataRoleType='Measure',order=0,isFlatHierarchy=False)
    a['bucketId']='AC';a['customName']=spec['label']
    if not source and spec.get('aggregation'): a['aggregationType']=spec['aggregation']
    p=base(50,spec['label']);p['pivotAssignments']=[a];vs=p['visualState'];vs.update(chartType='CARD',columnFieldsMapping={})
    vs['hiddenProperties_!!!_chartsMode']=dumps({'visualMode':'CARD','prevVisualMode':'CARD','isFromKpiSettings':False}).strip()
    vs['hiddenProperties_!!!_chartCustomTitle']=dumps({'showTitle':True,'editTitle':False,'customTitle':spec['label'],
        'formattedTitle':'<p style="font-family:Arial;font-size:13px;color:#36546A"><strong>'+html.escape(spec['label'])+'</strong></p>',
        'bgColor':'transparent','alignment':'','height':21,'preset':'DEFAULT','responsiveTitle':True,
        'isTitleEdited':True,'isTitleFormatEdited':True,'isDefaultPreset':False,'isDataLabelTitleAdded':False,'isTitleModified':True}).strip()
    vs['hiddenProperties_!!!_numberFormatting']=dumps({'enabled':False,'customFormat':{}}).strip()
    # Built-in dynamic mention tokens, not hardcoded financial values.
    def mention(token):
        value=html.escape(dumps({'name':'[$'+token+']','id':'[$'+token+']','label':'[$'+token+']'}).strip(),quote=True)
        return f'<span class="mention" data-id="{token.upper()}" data-value="{value}">[${token}]</span>'
    content='<p><span style="font-family:Arial;font-size:14px">'+mention('Title')+'</span></p><p><b><span style="font-family:Arial;font-size:28px">'+mention('Value')+'</span></b></p>'
    kpi={'instanceId':None,'layout':1,'previousLayout':1,'preset':0,'kpiFitMode':'Content',
         'isLayoutEdited':True,'isResponsiveTrellis':True,'title':{'enabled':True,'style':{'fontSize':14,'fontWeight':'bold','color':'#333333'}},
         'total':{'enabled':True,'showBlankAsLabel':True,'showCategoryLabel':True,'value':{'measure':None,'type':'total','isDefaultType':True},'style':{'fontSize':28,'fontWeight':'bold','color':'#333333'}},
         'variance':{'showVariance':False},'gridLayout':[{'id':'staticId_TopBottom','type':'text','name':'Value',
             'padding':0,'groupIds':[],'isHidden':False,'format':None,'measureKey':'AC','staticText':content,'dataType':4,
             'position':{'x':0,'y':0},'dimension':{'width':460,'height':75},'initialHeight':55,
             'percentageDimension':{'width':100,'height':100},'percentagePosition':{'x':0,'y':0},
             'layoutStyle':{'alignment':'center','bgColor':None,'justifyContent':'center'}}],
         'gridContainer':{'width':460,'height':75},'coreContainer':{'width':460,'height':101},
         'isSimplePreset':True,'isAutoLayout':True,'isDefaultPreset':True,'isDefaultLayout':True,
         'responsiveFontSize':True,'individualKpiControls':{},'groups':{},'framesMapping':{},'individualImageMeta':{}}
    vs['hiddenProperties_!!!_kpiControls']=dumps(kpi).strip()
    from .chart_filters import ensure_chart_filters
    return ensure_chart_filters(complete_card_state(p))

def column_chart(model,spec,registry,*,query_fields=()):
    """Native column chart; comparisonField selects integrated variance by default."""
    from .chart_filters import ensure_chart_filters
    from .linked_values import value_assignment
    p=base(50,spec['label'])
    category=field(model,spec['category'],'rows',0);category['bucketId']='category'
    measure=value_assignment(model,spec['field'],registry,query_fields=query_fields,bucket='AC',aggregation=spec.get('aggregation'))
    measure['customName']=spec.get('valueLabel',measure['columnName'])
    p['pivotAssignments']=[category,measure]
    title=card(model,{'field':spec['field'],'label':spec['label'],**({'aggregation':spec['aggregation']} if 'aggregation' in spec else {})},registry,query_fields=query_fields)
    p['visualState']['hiddenProperties_!!!_chartCustomTitle']=title['visualState']['hiddenProperties_!!!_chartCustomTitle']
    if spec.get('comparisonField'):
        from .forecast_review import comparison_chart
        baseline=value_assignment(model,spec['comparisonField'],registry,query_fields=query_fields,aggregation=spec.get('comparisonAggregation'))
        baseline['customName']=spec.get('comparisonLabel',baseline['columnName'])
        return comparison_chart(p,measure,baseline)
    return ensure_chart_filters(p)

def stacked_rectangles(slicers,cards, *, width=1600,grid_height=600,charts=0):
    if not 1000<=width<=2400 or grid_height<450: raise ValueError('Readable desktop canvas/grid minimum not met')
    if not 0<=slicers<=12 or not 0<=cards<=9: raise ValueError('Dashboard visual count outside supported layout')
    margin=24;gap=16;inner=width-2*margin;y=margin
    r={'header':{'x':margin,'y':y,'width':inner,'height':100}};y+=116
    for prefix,n,maxcols,h in [('slicer',slicers,4,150),('card',cards,3,132),('chart',charts,2,270)]:
        if n==0: continue
        cols=min(n,maxcols);w=(inner-(cols-1)*gap)/cols
        for i in range(n): r[f'{prefix}:{i}']={'x':margin+(i%cols)*(w+gap),'y':y+(i//cols)*(h+gap),'width':w,'height':h}
        y+=math.ceil(n/cols)*(h+gap)
    r['note']={'x':margin,'y':y,'width':inner,'height':44};y+=60
    r['navigator']={'x':margin,'y':y,'width':inner,'height':48};y+=64
    r['grid']={'x':margin,'y':y,'width':inner,'height':grid_height};height=y+grid_height+margin
    if height>8000: raise ValueError('Canvas exceeds native limits')
    for key,a in r.items():
        rect({'position':a,'dimension':a})
        for k,b in r.items():
            if key<k and overlap(a,b,gap-1e-7): raise ValueError('Layout collision')
    return {'width':width,'height':height,'unit':'pixel','rectangles':r}

def rectangles(slicers, cards, *, width=1920, grid_height=560, charts=0, pages=1, layout=None, viewport=None):
    from .stack_layout import fit_stack, reading_height, fill_columns
    if layout == 'stacked':
        stacked=stacked_rectangles(slicers,cards,width=width,grid_height=grid_height,charts=charts)
        if viewport is not None:
            height=max(stacked['height'],reading_height(width,viewport))
            if height>8000: raise ValueError('Canvas exceeds native limits')
            stacked['rectangles']['grid']['height']+=height-stacked['height']
            stacked['height']=height
        return stacked
    if not (1000 <= width <= 2400 and 0 <= slicers <= 12 and 0 <= cards <= 9 and charts >= 0 and grid_height >= 450):
        raise ValueError('Invalid desktop dashboard dimensions or visual count')
    slots = {'header','navigator','note','grid'} | {f'{k}:{i}' for k,n in
             [('slicer',slicers),('chart',charts),('card',cards)] for i in range(n)}
    margin,gap=24,16
    if isinstance(layout,dict):
        r=copy.deepcopy(layout['rectangles'])
        width,height=layout['width'],layout['height']
        if set(r)!=slots or layout.get('unit','pixel')!='pixel' or not 0<width<=8000:
            raise ValueError('Custom pixel layout must place every configured slot exactly once')
        if 'fitColumns' in layout:
            target=reading_height(width,viewport) if viewport is not None else round(width*59/100)
            height=max(height,target)
            bottom_margin=layout.get('bottomMargin',margin)
            if type(bottom_margin) is not int or bottom_margin<0: raise ValueError('Invalid bottomMargin')
            fill_columns(r,layout['fitColumns'],height-bottom_margin)
    elif layout is None or layout=='left-rail':
        r={}
        def place(key,x,y,w,h):
            r[key]=dict(x=x,y=y,width=w,height=h)
        right=width-margin
        top=margin+100+gap
        rail=max(216,width//6)
        main=margin+rail+gap if slicers else margin
        nav_h=24+36*max(1,pages) if slicers else 56
        note_y=top if slicers else top+nav_h+gap
        place('header',margin,margin,width-2*margin,100)
        place('navigator',margin,top,rail if slicers else right-margin,nav_h)
        def rows(prefix,count,cols,h,y):
            for start in range(0,count,cols):
                group=min(cols,count-start)
                for j,(x,w) in enumerate(fit_stack(main,right,gap,[1]*group)):
                    place(f'{prefix}:{start+j}',x,y,w,h)
                y+=h+gap
            return y
        note_y=rows('card',cards,3,132,note_y)
        place('note',main,note_y,right-main,44)
        grid_y=note_y+44+gap
        chart_h=max(220,round(width*0.15))
        chart_rows=math.ceil(charts/2)
        target=round(width*59/100) if viewport is None else reading_height(width,viewport)
        baseline=max(target-margin,grid_y+grid_height+chart_rows*(chart_h+gap))
        if slicers:
            first=top+nav_h+gap
            baseline=max(baseline,first+slicers*128+(slicers-1)*gap)
            for i,(y,h) in enumerate(fit_stack(first,baseline,gap,[1]*slicers)):
                place(f'slicer:{i}',margin,y,rail,h)
        grid_end=baseline-chart_rows*(chart_h+gap)
        place('grid',main,grid_y,right-main,grid_end-grid_y)
        rows('chart',charts,2,chart_h,grid_end+gap)
        height=baseline+margin
    else:
        raise ValueError('Use left-rail, stacked, or an explicit rectangle map')
    if not 0<height<=8000: raise ValueError('Canvas exceeds native limits')
    for key,a in r.items():
        rect({'position':a,'dimension':a})
        if a['x']+a['width']>width or a['y']+a['height']>height:
            raise ValueError('Visual outside canvas: '+key)
        if any(overlap(a,b,gap-1e-7) for other,b in r.items() if key<other):
            raise ValueError('Layout collision or insufficient gutter: '+key)
    return dict(width=width,height=height,unit='pixel',rectangles=r)

def dashboard(model,spec,owners,registry, *, query_fields=(),page_count=1):
    allowed={'name','owner','title','description','note','slicers','cards','charts','width','gridHeight','layout','viewport'}
    if set(spec)-allowed: raise ValueError('Unconsumed dashboard options')
    if spec['owner'] not in owners: raise ValueError('Dashboard source Planning owner unavailable')
    owner=owners[spec['owner']];sid=guid();layout=rectangles(len(spec['slicers']),len(spec['cards']),width=spec.get('width',1920),grid_height=spec.get('gridHeight',560),charts=len(spec.get('charts',[])),pages=page_count,layout=spec.get('layout'),viewport=spec.get('viewport'))
    sheet=sheet_properties(layout['width'],layout['height']);sp=sheet['properties']
    sp.update(excludedFilterContextAssignments={},filterContextUserConfig={})
    sp['canvasStyle']['background'].update(isEnabled=True,opacity=1)
    raw={f'sheets/{sid}/sheet.json':sheet};visuals=[];placements={};context=copy.deepcopy(owner.get('contexts',[]))
    context_keys={a['id'] for r in context for a in r['pivotAssignments']}
    if context_keys & {s['field'] for s in spec['slicers']}: raise ValueError('Do not duplicate external Context as an ordinary dashboard slicer')
    def add(kind,slot,p):
        vid=guid();r=layout['rectangles'][slot];p['position']={k:r[k] for k in ('x','y')};p['dimension']={k:r[k] for k in ('width','height')}
        p['layerProperties']['order']=len(visuals);placements[vid]=r
        raw[f'sheets/{sid}/visuals/{vid}/properties.json']={'$schema':schema('Planning/Properties'),'properties':p}
        visuals.append({'visualId':vid,'visualType':kind,'isEmbedded':False})
    banner=rich_text([[{'text':spec.get('title',spec['name']),'size':25,'color':'#FFFFFF','bold':True}],
        [{'text':spec.get('description',''),'color':'#D7E3ED'}],
        [{'text':'INPUT / FORECAST   ','color':'#FFD889','bold':True},{'text':'POWER BI   ','color':'#8BC5FF','bold':True},
         {'text':'FORMULA   ','color':'#DCC3FF','bold':True},{'text':'FROM SHEETS','color':'#9FE0D7','bold':True}]],name='Workspace header',banner=True)
    add('BI_TEXT','header',banner)
    all_filters=[]
    for i,s in enumerate(spec['slicers']):
        p=slicer(model,s);all_filters+=copy.deepcopy(p['visualState']['slicerFilterAssignments']);add('SUPER_FILTER',f'slicer:{i}',p)
    for i,c in enumerate(spec['cards']):
        p=card(model,c,registry,query_fields=query_fields)
        # KPI consumers receive selected scenario scope. This is a hidden filter
        # registration; only the Planning owner defines input Context identity.
        hidden=copy.deepcopy(context)
        for r in hidden: r.pop('isContextDimension',None);r['configuration']['hide']=True
        p['visualState']['embeddedSuperFilter']={'superFilterAssignments':hidden}
        forward_filters(p,all_filters);add('ANALYTICS_PLUS',f'card:{i}',p)
    for i,c in enumerate(spec.get('charts',[])):
        p=column_chart(model,c,registry,query_fields=query_fields);forward_filters(p,all_filters)
        add('ANALYTICS_PLUS',f'chart:{i}',p)
    add('BI_TEXT','note',rich_text([[{'text':spec.get('note','Plan inputs in the grid below.'),'size':12}]],name='Plan workbench'))
    nav_rect=layout['rectangles']['navigator']
    direction='vertical' if nav_rect['width'] < layout['width']/2 else 'horizontal'
    add('BI_RUNTIME_INPUT','navigator',page_navigator(direction))
    visuals.append({'visualId':owner['visualId'],'visualType':'PLANNING','isEmbedded':True})
    from .public_alignment import embedded_placement
    placement = owner.get('placementIds')
    origin = placement['originEntityId'] if placement else owner['sheetId']
    visual = placement['visualId'] if placement else owner['visualId']
    sp['reactiveVisualProperties'] = [embedded_placement(origin, visual, layout['rectangles']['grid'])]
    placements[owner['visualId']]=layout['rectangles']['grid']
    declaration={'recordGuid':sid,'displayName':spec['name'],'sheetType':'REPORTING','isHidden':False,'workloadItemEntityVisuals':visuals}
    return declaration,raw,{'sheetGuid':sid,'name':spec['name'],'ownerGuid':owner['visualId'], 'placementIds':placement,
        'placements':placements,'layout':layout,'construction':'generated-selected-branches','runtime':'not-tested'}
