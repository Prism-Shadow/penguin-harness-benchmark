#!/bin/bash
set -euo pipefail
mode=${1:-}
case "$mode" in
  --verify-published|--verify-complete|--materialize) ;;
  *) echo 'usage: provision-target-gems --verify-published|--verify-complete MIRROR LOCKFILE; --materialize MIRROR LOCKFILE RECEIPTS' >&2; exit 64 ;;
esac
export TARGET_MODE="$mode" TARGET_MIRROR="${2:?mirror required}" TARGET_LOCKFILE="${3:?lockfile required}" TARGET_RECEIPT_DIR="${4:-}"
ruby <<'RUBY'
require 'digest'
require 'fileutils'
require 'json'
require 'rubygems/package'

def regular(path)
  abort "not a regular file: #{path}" unless File.file?(path) && !File.symlink?(path)
end

def archive_check(path, name, version, platform, sha, bytes)
  regular(path)
  abort "archive hash mismatch: #{path}" unless Digest::SHA256.file(path).hexdigest == sha
  abort "archive size mismatch: #{path}" unless File.size(path) == bytes
  spec = Gem::Package.new(path).spec
  abort "archive identity mismatch: #{path}" unless [spec.name, spec.version.to_s, spec.platform.to_s] == [name, version, platform]
end

def check_receipt(receipt, item, lock_sha)
  expected = {
    'schema' => 'task-source-bound-gem-receipt-v1', 'name' => item.fetch('name'),
    'version' => item.fetch('version'), 'lockfile_sha256' => lock_sha,
    'upstream_repository' => item.fetch('upstream_repository'),
    'commit' => item.fetch('commit'), 'tree' => item.fetch('tree'),
    'source_archive_sha256' => item.fetch('source_archive_sha256'),
    'registry_archive_available' => false, 'registry_archive_equivalence_claimed' => false,
    'payload_matches_authenticated_source' => true
  }
  expected.each { |key, value| abort "source receipt mismatch: #{key}" unless receipt[key] == value }
end

mirror = ENV.fetch('TARGET_MIRROR')
lockfile = ENV.fetch('TARGET_LOCKFILE')
mode = ENV.fetch('TARGET_MODE')
manifest_path = File.join(mirror, 'manifest.json')
regular(manifest_path)
regular(lockfile)
manifest = JSON.parse(File.read(manifest_path))
abort 'target mirror schema mismatch' unless manifest['schema'] == 'task-target-gem-mirror-v1'
lock_sha = Digest::SHA256.file(lockfile).hexdigest
abort 'target lockfile hash mismatch' unless lock_sha == manifest['lockfile_sha256']
archives_dir = File.join(mirror, 'archives')
published = manifest.fetch('published_archives')
source = manifest.fetch('source_archives')
abort 'published archive count mismatch' unless published.length == 163
abort 'source archive inventory mismatch' unless source.map { |item| item['name'] }.sort == %w[meta_request mimemagic]
published.each do |item|
  abort 'noncanonical published filename' unless item.fetch('filename') == "#{item.fetch('name')}-#{item.fetch('version')}.gem"
  archive_check(File.join(archives_dir, item.fetch('filename')), item.fetch('name'), item.fetch('version'), item.fetch('platform'), item.fetch('sha256'), item.fetch('bytes'))
end
source.each do |item|
  path = File.join(mirror, item.fetch('source_archive'))
  regular(path)
  abort "source archive hash mismatch: #{path}" unless Digest::SHA256.file(path).hexdigest == item.fetch('source_archive_sha256')
  abort "source archive size mismatch: #{path}" unless File.size(path) == item.fetch('source_archive_bytes')
  abort 'noncanonical source gem filename' unless item.fetch('gem_archive') == "archives/#{item.fetch('name')}-#{item.fetch('version')}.gem"
end
locked = File.read(lockfile).scan(/^    ([A-Za-z0-9_-]+) \(([^)]+)\)$/).reject { |name, version| version.end_with?('-java') }
provided = (published + source).map { |item| [item.fetch('name'), item.fetch('version')] }
abort 'target lock archive closure mismatch' unless locked.sort == provided.sort && provided.uniq.length == 165

if mode == '--materialize'
  receipt_dir = ENV.fetch('TARGET_RECEIPT_DIR')
  abort 'receipt directory required' if receipt_dir.empty?
  checked = source.map do |item|
    receipt_path = File.join(receipt_dir, "#{item.fetch('name')}.json")
    regular(receipt_path)
    receipt = JSON.parse(File.read(receipt_path))
    check_receipt(receipt, item, lock_sha)
    archive = receipt.fetch('gem_archive')
    regular(archive)
    archive_check(archive, item.fetch('name'), item.fetch('version'), 'ruby', receipt.fetch('gem_archive_sha256'), File.size(archive))
    destination = File.join(mirror, item.fetch('gem_archive'))
    if File.exist?(destination)
      regular(destination)
      abort "refusing conflicting source gem overwrite: #{destination}" unless Digest::SHA256.file(destination).hexdigest == receipt.fetch('gem_archive_sha256')
    end
    [item, receipt_path, receipt, archive, destination]
  end
  FileUtils.mkdir_p(File.join(mirror, 'source-receipts'))
  checked.each do |item, receipt_path, receipt, archive, destination|
    FileUtils.cp(archive, destination)
    item['gem_archive_pending'] = false
    item['gem_archive_sha256'] = receipt.fetch('gem_archive_sha256')
    item['gem_archive_bytes'] = File.size(archive)
    item['gem_provenance_kind'] = 'same_version_source_rebuild'
    item['gem_provenance'] = "#{item.fetch('upstream_repository')}/tree/#{item.fetch('commit')}"
    item['source_receipt'] = File.join('source-receipts', "#{item.fetch('name')}.json")
    item['source_receipt_sha256'] = Digest::SHA256.file(receipt_path).hexdigest
    FileUtils.cp(receipt_path, File.join(mirror, item.fetch('source_receipt')))
  end
  manifest['complete_for_target_install'] = true
  manifest['blocking_assets'] = []
  tmp = "#{manifest_path}.tmp.#{$$}"
  File.write(tmp, JSON.pretty_generate(manifest) + "\n")
  File.rename(tmp, manifest_path)
end

if mode != '--verify-published' || manifest['complete_for_target_install'] == true
  abort 'target source-built gems are still pending' unless manifest['complete_for_target_install'] == true
  source.each do |item|
    abort 'source gem pending' unless item['gem_archive_pending'] == false
    archive_check(File.join(mirror, item.fetch('gem_archive')), item.fetch('name'), item.fetch('version'), 'ruby', item.fetch('gem_archive_sha256'), item.fetch('gem_archive_bytes'))
    receipt_path = File.join(mirror, item.fetch('source_receipt'))
    regular(receipt_path)
    abort 'source receipt hash mismatch' unless Digest::SHA256.file(receipt_path).hexdigest == item.fetch('source_receipt_sha256')
    receipt = JSON.parse(File.read(receipt_path))
    check_receipt(receipt, item, lock_sha)
    abort 'source gem receipt disagrees' unless receipt.fetch('gem_archive_sha256') == item.fetch('gem_archive_sha256')
  end
  expected_files = provided.map { |name, version| "#{name}-#{version}.gem" }.sort
  actual_files = Dir.entries(archives_dir).reject { |name| name == '.' || name == '..' }.sort
  abort 'unexpected or missing target archive' unless actual_files == expected_files
end
puts JSON.generate(status: 'target_mirror_verified', published_archives: published.length, source_gems: source.length, complete: manifest['complete_for_target_install'])
RUBY
