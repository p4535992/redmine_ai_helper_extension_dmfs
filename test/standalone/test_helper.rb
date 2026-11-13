# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later

if defined?(Rails) || defined?(Redmine::Plugin) || defined?(DmsfFile)
  raise "Run standalone tests in a fresh Ruby process, outside Redmine/Rails"
end

require "minitest/autorun"
require "rubygems"
require "ostruct"

$LOAD_PATH.unshift(File.expand_path("support", __dir__))

module Redmine
  module Plugin
    class << self
      attr_accessor :installed, :version

      def installed?(name)
        name == :redmine_dmsf && installed
      end

      def find(name)
        raise "Plugin not installed" unless installed?(name)

        OpenStruct.new(version: version)
      end
    end
  end
end

class AiHelperSetting
  class << self
    attr_accessor :send_enabled, :attachment_max_size_mb

    def attachment_send_enabled?
      send_enabled
    end
  end
end

module Setting
  class << self
    # Serialized plugin setting written by RedmineAiHelperDmsf::Settings.
    attr_accessor :plugin_redmine_ai_helper_extension_dmfs
  end

  def self.host_name
    "redmine.example"
  end

  def self.protocol
    "https"
  end
end

module TestRouteHelpers
  def self.view_dmsf_file_url(id, filename:, host:, protocol:)
    raise "Filename is required" if filename.nil? || filename.empty?

    "#{protocol}://#{host}/dmsf/files/#{id}/view"
  end
end

module Rails
  def self.application
    OpenStruct.new(routes: OpenStruct.new(url_helpers: TestRouteHelpers))
  end
end

class User
  class << self
    attr_accessor :current
  end

  attr_accessor :denied_permissions

  def initialize
    @denied_permissions = []
  end

  def allowed_to?(permission, project)
    !denied_permissions.include?([permission, project.id])
  end
end

class Project
  class << self
    attr_accessor :records

    def find_by(id:)
      records.find { |project| project.id == id }
    end
  end

  attr_reader :id, :name
  attr_accessor :dmsf_enabled

  def initialize(id, name: "Example project")
    @id = id
    @name = name
    @dmsf_enabled = true
  end

  def module_enabled?(name)
    name == :dmsf && dmsf_enabled
  end
end

class DmsfFolder
  class << self
    attr_accessor :denied, :permission_calls

    def permissions?(folder, allow_system:, file:)
      permission_calls << { folder: folder, allow_system: allow_system, file: file }
      !denied.include?(folder)
    end
  end
end

class DmsfFileRevision
  attr_reader :id, :file_reads
  attr_accessor :deleted, :visible, :attachment

  def initialize(id, attachment:)
    @id = id
    @attachment = attachment
    @deleted = false
    @visible = true
    @file_reads = 0
  end

  def deleted?
    deleted
  end

  def visible?(_user)
    !deleted && visible
  end

  def file
    @file_reads += 1
    attachment
  end
end

class DmsfFile
  class Scope
    def initialize(records)
      @records = records
    end

    def where(project_id:)
      self.class.new(@records.select { |file| project_id.include?(file.project_id) })
    end

    def includes(*)
      self
    end

    def find_each(batch_size:)
      raise "Expected bounded database batches" unless batch_size <= 100

      @records.each { |file| yield file }
    end

    def find_by(id:)
      @records.find { |file| file.id == id }
    end
  end

  class << self
    attr_accessor :records, :search_result, :search_error, :search_calls, :visible_calls

    def visible
      self.visible_calls += 1
      Scope.new(records.reject(&:deleted?))
    end

    def search(*arguments)
      search_calls << arguments
      raise search_error if search_error

      search_result
    end
  end

  attr_accessor :id, :project, :name, :title, :description, :revision, :folder,
                :deleted

  def initialize(id, project:, revision:, name: "spec.pdf")
    @id = id
    @project = project
    @revision = revision
    @name = name
    @title = "Technical Specification"
    @description = "Project reference"
    @folder = Object.new
    @deleted = false
  end

  def project_id
    project.id
  end

  def deleted?
    deleted
  end

  def last_revision
    revision
  end

  def dmsf_folder
    folder
  end

  def dmsf_path_str
    "Specifications/#{title}"
  end

  def version
    "2.1"
  end
end

module RedmineDmsf
  class << self
    attr_accessor :xapian_available
  end
end

module RubyLLM
  class Attachment
    attr_reader :source, :filename

    def initialize(source, filename:)
      @source = source
      @filename = filename
    end
  end
end

class FakeAttachment
  attr_accessor :bytes, :attached, :declared_size
  attr_reader :downloads

  def initialize(bytes = "%PDF-1.7 PRIVATE-DOCUMENT-MARKER".b)
    @bytes = bytes
    @attached = true
    @declared_size = bytes.bytesize
    @downloads = 0
  end

  def attached?
    attached
  end

  def blob
    OpenStruct.new(byte_size: declared_size)
  end

  def download
    @downloads += 1
    bytes.dup
  end
end

require_relative "../../lib/redmine_ai_helper_dmsf/dmsf_tools"
