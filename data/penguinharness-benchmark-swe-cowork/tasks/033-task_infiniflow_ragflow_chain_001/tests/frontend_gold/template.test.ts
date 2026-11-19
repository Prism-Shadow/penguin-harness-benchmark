import * as create from '@/pages/user-setting/compilation-templates/create-next/utils';
import * as edit from '@/pages/user-setting/compilation-templates/edit-next/utils';

for (const [name, implementation] of [['create',create],['edit',edit]] as const) {
 test(`${name} roundtrips Wiki mode and blueprint without turning metadata into sections`,()=>{
  for(const mode of ['entity','topic']) {
   const detail:any={id:'id',name:'Research',kind:'wiki',config:{kind:'wiki',llm_id:'model',mode,example:'Write grounded pages\n\n# Example\nEvidence',global_rules:'cite sources'}};
   const form=implementation.transformDetailToForm(detail);
   expect(form.config).toMatchObject({mode,use_blueprint:true,instruction:'Write grounded pages',page_example:'# Example\nEvidence'});
   const payload=implementation.transformTemplateToPayload(form);
   expect(payload.config).toMatchObject({mode,llm_id:'model',example:detail.config.example});
   expect(payload.config.instruction).toBeUndefined();
   const again=implementation.transformDetailToForm(payload as any);
   expect(again.config.mode).toBe(mode);
   expect(again.config.instruction).toBe('Write grounded pages');
   again.config.use_blueprint=false;
   expect(implementation.transformTemplateToPayload(again).config.example).toBe('');
  }
 });
 test(`${name} legacy and builtin templates default to entity and preserve unrelated sections`,()=>{
  const config=implementation.buildConfigFromBuiltin({config:{example:'',claims:{description:'facts',fields:[{subject:'person',claim:'did something'}]}}} as any,'wiki','chosen');
  expect(config.mode).toBe('entity');expect(config.use_blueprint).toBe(false);expect(config.claims).toMatchObject({description:'facts'});
  const tree=implementation.buildConfigFromBuiltin({config:{raptor:{max_token:800,rechunk:true}}} as any,'tree','chosen');
  expect(tree.raptor).toMatchObject({max_token:800,rechunk:true});
 });
}
