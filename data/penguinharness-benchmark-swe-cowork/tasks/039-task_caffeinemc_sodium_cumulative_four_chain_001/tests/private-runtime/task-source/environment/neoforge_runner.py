"""Execute the NeoForge game-init injection with external loader/game I/O ports."""
from pathlib import Path
import json, os, subprocess, tomllib
from module_runner import build, packaged_resource
from native_runtime import external_loader_classpath, hydrate_game_resources, java_command
from loader_runner import MINECRAFT

MODLIST='''package net.neoforged.fml;
import java.util.*;
import java.lang.reflect.*;
import java.lang.annotation.ElementType;
import net.neoforged.neoforgespi.language.IModInfo;
import net.neoforged.neoforgespi.language.ModFileScanData;
import org.objectweb.asm.Type;
public class ModList {
 private static final ModList INSTANCE=new ModList();
 public static ModList get(){return INSTANCE;}
 public List<IModInfo> getMods(){return List.of(info("sodium"),info("extension"),info("annotated"));}
 public Optional<ModContainer> getModContainerById(String id){return Optional.of(new ModContainer(info(id)));}
 public List<ModFileScanData> getAllScanData(){
  var data=new ModFileScanData();
  data.getAnnotations().add(new ModFileScanData.AnnotationData(
   Type.getType(net.caffeinemc.mods.sodium.api.config.ConfigEntryPointForge.class),ElementType.TYPE,
   Type.getObjectType("NeoForgeProductionChecks$AnnotationExtension"),"",Map.of("value","annotated")));
  return List.of(data);
 }
 static IModInfo info(String id){return (IModInfo)Proxy.newProxyInstance(ModList.class.getClassLoader(),new Class[]{IModInfo.class},(p,m,a)->switch(m.getName()){
  case "getModId","getDisplayName" -> id;
  case "getVersion" -> new org.apache.maven.artifact.versioning.DefaultArtifactVersion("fixture-1");
  case "getModProperties" -> id.equals("extension")?Map.of("sodium:config_api_user","NeoForgeProductionChecks$PropertyExtension","frex:flawless_frames_handler","NeoForgeProductionChecks$FlawlessHandler"):Map.of();
  default -> null;
 });}
}'''
CONTAINER='''package net.neoforged.fml;
public class ModContainer {
 public static Object registeredConfigScreen;
 private final net.neoforged.neoforgespi.language.IModInfo info;
 public ModContainer(net.neoforged.neoforgespi.language.IModInfo info){this.info=info;}
 public net.neoforged.neoforgespi.language.IModInfo getModInfo(){return info;}
 public <T extends IExtensionPoint> void registerExtensionPoint(Class<T> type,T extension){
  if(type==net.neoforged.neoforge.client.gui.IConfigScreenFactory.class)registeredConfigScreen=extension;
 }
}'''

def run(root,cache):
    status,outputs=build(root,cache)
    if status:return status
    root,cache=Path(root),Path(cache)
    out=cache/'neoforge-production';out.mkdir(exist_ok=True)
    source=out/'sources';source.mkdir(exist_ok=True);files=[]
    for name,content in [('net/neoforged/fml/ModList.java',MODLIST),('net/neoforged/fml/ModContainer.java',CONTAINER),('net/minecraft/client/Minecraft.java',MINECRAFT)]:
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content);files.append(str(path))
    probes=Path(__file__).parent/'native'
    files.extend(str(probes/name) for name in ['NeoForgeProductionChecks.java','GeometryProductionChecks.java'])
    cp=outputs['neoforge_classpath']
    result=subprocess.run(['javac','-proc:none','--release','21','-cp',cp,'-d',str(out),*files],capture_output=True,text=True,timeout=120)
    print(result.stdout+result.stderr,end='',flush=True)
    if result.returncode:return 10
    descriptor=out/'META-INF/services/net.caffeinemc.mods.sodium.client.services.PlatformRuntimeInformation'
    descriptor.parent.mkdir(parents=True,exist_ok=True);descriptor.write_text('GeometryProductionChecks$Platform\n')
    try:
        bootstrap_service='META-INF/services/net.neoforged.neoforgespi.earlywindow.GraphicsBootstrapper'
        service,names=packaged_resource(outputs,'neoforge',bootstrap_service)
        providers=[line.split('#',1)[0].strip() for line in service.decode().splitlines() if line.split('#',1)[0].strip()]
        assert providers,'NeoForge packaged early graphics bootstrap service is empty'
        for provider in providers:
            assert provider.replace('.','/')+'.class' in names,'NeoForge early service provider class is absent: '+provider
        destination=out/bootstrap_service;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(service)
        metadata,names=packaged_resource(outputs,'neoforge','META-INF/neoforge.mods.toml')
        class_list=out/'packaged-classes.json'
        class_list.write_text(json.dumps(sorted(name[:-6].replace('/','.') for name in names if name.endswith('.class') and not name.startswith('META-INF/'))))
        registered=[item['config'] for item in tomllib.loads(metadata.decode()).get('mixins',[])]
        assert registered,'NeoForge metadata omits mixin registrations'
        descriptors=[]
        for index, resource in enumerate(registered):
            mixin_raw,names=packaged_resource(outputs,'neoforge',resource)
            mixin=json.loads(mixin_raw)
            prefix=mixin.get('package','')
            for item in mixin.get('client',[])+mixin.get('mixins',[]):
                name=prefix+'.'+item if prefix else item
                assert name.replace('.','/')+'.class' in names,'NeoForge packaged mixin class is absent: '+name
            descriptor_file=out/('registered-mixins-'+str(index)+'.json')
            descriptor_file.write_bytes(mixin_raw);descriptors.append(str(descriptor_file))
    except AssertionError as error:
        print('AssertionError:',error,flush=True);return 1
    hydrate_game_resources(outputs['fabric_classpath'],out)
    runtime_cp=external_loader_classpath(cp,out,{'net/neoforged/fml/ModList.class'})
    result=subprocess.run(java_command(out,runtime_cp,'NeoForgeProductionChecks',str(class_list),*descriptors),cwd=out,env=os.environ|{'XDG_SESSION_TYPE':'wayland'},capture_output=True,text=True,timeout=90)
    output=result.stdout+result.stderr;print(output,end='',flush=True);(out/'execution.log').write_text(output)
    if result.returncode and any(v in output for v in ['NoSuchMethodError','NoSuchFieldError','UnsatisfiedLinkError','NoClassDefFoundError']):return 12
    if result.returncode==0 and not any(line.startswith('NEOFORGE_PRODUCTION_PASS ') for line in output.splitlines()):
        print('AssertionError: production process exited before required NEOFORGE_PRODUCTION_PASS checks completed',flush=True)
        return 1
    return result.returncode
