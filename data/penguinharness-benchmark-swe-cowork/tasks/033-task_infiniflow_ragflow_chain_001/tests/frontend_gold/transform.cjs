const esbuild = require('esbuild');
const babel = require('@babel/core');
module.exports = {
 process(source, filename) {
  const {code} = esbuild.transformSync(source, {loader:filename.endsWith('tsx')?'tsx':filename.endsWith('ts')?'ts':'jsx',format:'cjs',target:'es2022',jsx:'automatic',sourcemap:'inline',sourcefile:filename});
  return {code:babel.transformSync(code,{plugins:[require('babel-plugin-jest-hoist')],babelrc:false,configFile:false,filename}).code};
 }
};
