# frozen_string_literal: true
# SPDX-License-Identifier: GPL-3.0-or-later

require_relative "test_helper"

# Tests execute the production provider. Only its external dependencies are fake;
# the authorization, search, validation and attachment handling are never stubbed.
class DmsfToolsTest < Minitest::Test
  def setup
    @previous_opt_in = ENV["REDMINE_AI_HELPER_DMSF_ENABLED"]
    ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] = "1"
    Redmine::Plugin.installed = true
    Redmine::Plugin.version = "5.0.5"
    AiHelperSetting.send_enabled = true
    AiHelperSetting.attachment_max_size_mb = 3
    RedmineDmsf.xapian_available = false
    User.current = User.new
    @project = Project.new(1)
    @other_project = Project.new(2, name: "Restricted project")
    Project.records = [@project, @other_project]
    @provider = RedmineAiHelperDmsf::DmsfTools.new
    @provider.allowed_projects = [@project]
    DmsfFolder.denied = []
    DmsfFolder.permission_calls = []
    DmsfFile.records = []
    DmsfFile.search_result = [[], 0]
    DmsfFile.search_error = nil
    DmsfFile.search_calls = []
    DmsfFile.visible_calls = 0
    @attachment = FakeAttachment.new
    @revision = DmsfFileRevision.new(87, attachment: @attachment)
    @file = DmsfFile.new(42, project: @project, revision: @revision)
    DmsfFile.records << @file
  end

  def teardown
    ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] = @previous_opt_in
    Setting.plugin_redmine_ai_helper_extension_dmfs = nil
  end

  def test_plugin_absence_blocks_search_and_analysis_before_storage_access
    Redmine::Plugin.installed = false

    refute RedmineAiHelperDmsf::DmsfTools.enabled?
    assert_error(@provider.search_files(query: "technical"), /unavailable/)
    assert_error(@provider.analyze_file(file_id: 42), /unavailable/)
    assert_equal 0, DmsfFile.visible_calls
    assert_no_document_read
  end

  def test_each_opt_in_is_required
    [nil, "0", "true"].each do |value|
      ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] = value
      refute RedmineAiHelperDmsf::DmsfTools.enabled?
      assert_error(@provider.search_files(query: "technical"), /unavailable/)
    end
    ENV["REDMINE_AI_HELPER_DMSF_ENABLED"] = "1"
    AiHelperSetting.send_enabled = false
    refute RedmineAiHelperDmsf::DmsfTools.enabled?
    assert_error(@provider.analyze_file(file_id: 42), /unavailable/)
    AiHelperSetting.send_enabled = true
    assert RedmineAiHelperDmsf::DmsfTools.enabled?
    assert_no_document_read
  end

  def test_legacy_dmsf_without_supported_storage_api_is_not_available
    Redmine::Plugin.version = "4.2.4"

    refute RedmineAiHelperDmsf::DmsfTools.available?
    assert_error(@provider.search_files(query: "technical"), /unavailable/)
    assert_error(@provider.analyze_file(file_id: 42), /unavailable/)
    assert_no_document_read
  end

  def test_missing_dmsf_model_fails_closed
    original = Object.send(:remove_const, :DmsfFileRevision)

    refute RedmineAiHelperDmsf::DmsfTools.available?
    assert_error(@provider.search_files(query: "technical"), /unavailable/)
    assert_no_document_read
  ensure
    Object.const_set(:DmsfFileRevision, original) if original
  end

  def test_only_two_read_only_functions_are_exposed
    registry = RedmineAiHelperDmsf::DmsfTools.function_registry
    assert_equal [:analyze_file, :search_files], registry.keys.sort
    assert registry.values.all? { |function| function[:write] == false }
  end

  def test_ai_helper_project_scope_is_enforced_by_both_public_tools
    @provider.allowed_projects = []

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.search_files(query: "technical", project_id: 1), /not accessible/)
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_dmsf_project_permission_is_enforced_by_both_public_tools
    User.current.denied_permissions << [:view_dmsf_files, @project.id]

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.search_files(query: "technical", project_id: 1), /not accessible/)
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_disabled_project_module_is_enforced
    @project.dmsf_enabled = false

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_folder_acl_is_checked_explicitly
    DmsfFolder.denied << @file.folder

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    refute_empty DmsfFolder.permission_calls
    assert DmsfFolder.permission_calls.all? { |call| call[:allow_system] && call[:file] }
    assert_no_document_read
  end

  def test_deleted_files_are_rejected
    @file.deleted = true

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_deleted_current_revisions_are_rejected
    @revision.deleted = true

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_invisible_revisions_are_rejected
    @revision.visible = false

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_missing_revision_is_rejected
    @file.revision = nil

    assert_empty @provider.search_files(query: "technical")[:documents]
    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_revision_permission_is_checked_before_opening_attachment
    User.current.denied_permissions << [:view_dmsf_file_revisions, @project.id]

    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_permissions_are_rechecked_between_search_and_analysis
    assert_equal [42], ids(@provider.search_files(query: "technical"))
    DmsfFolder.denied << @file.folder

    assert_error(@provider.analyze_file(file_id: 42), /not accessible/)
    assert_no_document_read
  end

  def test_search_returns_current_revision_metadata_without_reading_document_bytes
    result = @provider.search_files(query: "  TECHNICAL  ", project_id: "1")

    assert_equal [42], ids(result)
    assert_equal 87, result[:documents].first[:revision_id]
    assert_equal "2.1", result[:documents].first[:version]
    assert_equal "https://redmine.example/dmsf/files/42/view", result[:documents].first[:url]
    assert_equal false, result[:truncated]
    refute_includes result.inspect, "PRIVATE-DOCUMENT-MARKER"
    assert_no_document_read
  end

  def test_invalid_queries_are_rejected_before_database_access
    [nil, false, 123, "", " \n\t ", "x" * 201].each do |query|
      assert_error(@provider.search_files(query: query), /query/)
    end
    assert_equal 0, DmsfFile.visible_calls
  end

  def test_ids_are_positive_integers_without_float_or_string_coercion
    [nil, 0, -1, 42.0, 42.5, true, "42.0", "42x", "-42", " 42 "].each do |id|
      assert_error(@provider.analyze_file(file_id: id), /positive integer/)
    end
    [0, -1, 1.0, true, "1.0", "1x"].each do |id|
      assert_error(@provider.search_files(query: "technical", project_id: id), /positive integer/)
    end
    assert_no_document_read
  end

  def test_equal_result_count_is_not_reported_as_truncated
    make_matching_files(3)
    result = @provider.search_files(query: "technical", limit: 3)

    assert_equal 3, result[:documents].length
    assert_equal false, result[:truncated]
  end

  def test_extra_match_is_reported_as_truncated
    make_matching_files(4)
    result = @provider.search_files(query: "technical", limit: 3)

    assert_equal 3, result[:documents].length
    assert_equal true, result[:truncated]
  end

  def test_result_limit_is_capped_and_never_becomes_unbounded
    make_matching_files(21)
    result = @provider.search_files(query: "technical", limit: 10_000)

    assert_equal 20, result[:documents].length
    assert_equal true, result[:truncated]
  end

  def test_metadata_scan_is_bounded_when_no_documents_match
    DmsfFile.records = Array.new(2_050, @file)
    result = @provider.search_files(query: "does-not-match-anything")

    assert_empty result[:documents]
    assert_equal 2_000, result[:scanned]
    assert_equal true, result[:truncated]
  end

  def test_xapian_is_not_called_when_unavailable
    result = @provider.search_files(query: "only-in-document-body")

    assert_empty result[:documents]
    assert_empty DmsfFile.search_calls
    assert_equal "unavailable", result[:content_search]
  end

  def test_full_text_search_is_enabled_by_default
    assert RedmineAiHelperDmsf::Settings.full_text_search_enabled?
    assert_equal({ "full_text_search_enabled" => "1" }, RedmineAiHelperDmsf::Settings.values)
  end

  def test_stored_settings_without_the_key_fall_back_to_the_default
    Setting.plugin_redmine_ai_helper_extension_dmfs = {}

    assert RedmineAiHelperDmsf::Settings.full_text_search_enabled?
    assert_equal "1", RedmineAiHelperDmsf::Settings.values["full_text_search_enabled"]
  end

  def test_disabled_full_text_search_skips_dmsf_search_and_reports_disabled
    RedmineDmsf.xapian_available = true
    DmsfFile.search_result = [[@file], 1]
    RedmineAiHelperDmsf::Settings.update("full_text_search_enabled" => "0")

    result = @provider.search_files(query: "only-in-document-body")

    assert_empty result[:documents]
    assert_empty DmsfFile.search_calls
    assert_equal "disabled", result[:content_search]
    assert_equal false, result[:content_search_limited]
    assert_no_document_read
  end

  def test_disabled_full_text_search_keeps_current_metadata_matches
    RedmineAiHelperDmsf::Settings.update("full_text_search_enabled" => "0")

    result = @provider.search_files(query: "technical")

    assert_equal [42], ids(result)
    assert_equal "current_metadata", result[:documents].first[:match_source]
    assert_equal "disabled", result[:content_search]
  end

  def test_settings_update_ignores_unknown_keys_and_missing_values
    RedmineAiHelperDmsf::Settings.update("full_text_search_enabled" => "1")
    RedmineAiHelperDmsf::Settings.update("unknown_setting" => "0")
    assert RedmineAiHelperDmsf::Settings.full_text_search_enabled?

    RedmineAiHelperDmsf::Settings.update({})
    assert RedmineAiHelperDmsf::Settings.full_text_search_enabled?
    assert_equal({ "full_text_search_enabled" => "1" },
                 Setting.plugin_redmine_ai_helper_extension_dmfs)
  end

  def test_settings_update_normalizes_unexpected_values_to_disabled
    RedmineAiHelperDmsf::Settings.update("full_text_search_enabled" => "yes")

    refute RedmineAiHelperDmsf::Settings.full_text_search_enabled?
    assert_equal "0", RedmineAiHelperDmsf::Settings.values["full_text_search_enabled"]
  end

  def test_dmsf_files_count_pair_adds_content_matches_and_deduplicates
    RedmineDmsf.xapian_available = true
    DmsfFile.search_result = [[@file, @file], 2]
    result = @provider.search_files(query: "only-in-document-body")

    assert_equal [42], ids(result)
    assert_equal 1, DmsfFile.search_calls.length
    assert_equal ["only-in-document-body", [@project], { limit: 2_000 }, User.current], DmsfFile.search_calls.first
    assert_equal "attempted", result[:content_search]
    assert_equal "dmsf_search", result[:documents].first[:match_source]
    assert_no_document_read
  end

  def test_dmsf_result_count_warns_about_backend_truncation
    RedmineDmsf.xapian_available = true
    DmsfFile.search_result = [[@file], 20]
    result = @provider.search_files(query: "only-in-document-body")

    assert_equal [42], ids(result)
    assert_equal true, result[:content_search_limited]
    assert_equal true, result[:truncated]
  end

  def test_metadata_and_content_matches_are_deduplicated
    RedmineDmsf.xapian_available = true
    DmsfFile.search_result = [[@file], 1]

    result = @provider.search_files(query: "technical")
    assert_equal [42], ids(result)
    assert_equal "current_metadata", result[:documents].first[:match_source]
  end

  def test_xapian_hits_cannot_escape_project_scope_or_folder_acls
    RedmineDmsf.xapian_available = true
    foreign_file = DmsfFile.new(43, project: @other_project, revision: @revision)
    forbidden_file = DmsfFile.new(44, project: @project, revision: @revision)
    DmsfFolder.denied << forbidden_file.folder
    DmsfFile.search_result = [[foreign_file, forbidden_file, @file], 3]

    assert_equal [42], ids(@provider.search_files(query: "only-in-document-body"))
    assert_no_document_read
  end

  def test_deleted_xapian_hits_are_rechecked
    RedmineDmsf.xapian_available = true
    @file.deleted = true
    DmsfFile.search_result = [[@file], 1]

    assert_empty @provider.search_files(query: "only-in-document-body")[:documents]
    assert_no_document_read
  end

  def test_xapian_errors_are_not_misreported_as_a_successful_empty_search
    RedmineDmsf.xapian_available = true
    DmsfFile.search_error = RuntimeError.new("Xapian backend failed")

    assert_raises(RuntimeError) { @provider.search_files(query: "technical") }
  end

  def test_unexpected_dmsf_search_shapes_surface_as_integration_errors
    RedmineDmsf.xapian_available = true

    [nil, [1, [@file]], [[Object.new], 1], [[@file], 0]].each do |response|
      DmsfFile.search_result = response
      assert_raises(TypeError) { @provider.search_files(query: "technical") }
    end
  end

  def test_pdf_analysis_passes_an_in_memory_attachment_and_source_link
    result = @provider.analyze_file(file_id: "42", question: "Key sections?")

    assert_equal "Document summary from the test model", result[:analysis]
    assert_equal "https://redmine.example/dmsf/files/42/view", result[:document][:url]
    assert_equal 1, @attachment.downloads
    assert_equal 1, @provider.llm_calls.length
    call = @provider.llm_calls.first
    assert_includes call[:prompt], "Key sections?"
    assert_includes call[:prompt], "untrusted"
    assert_equal 1, call[:file_paths].length
    attachment = call[:file_paths].first
    assert_instance_of RubyLLM::Attachment, attachment
    assert_instance_of StringIO, attachment.source
    assert_equal @attachment.bytes, attachment.source.string
    assert_equal "spec.pdf", attachment.filename
    refute_includes result.inspect, "PRIVATE-DOCUMENT-MARKER"
    refute_includes result.inspect, "/tmp/"
  end

  def test_oversized_declared_blob_is_rejected_without_download
    @attachment.declared_size = 4 * 1024 * 1024

    assert_error(@provider.analyze_file(file_id: 42), /size limit/)
    assert_equal 0, @attachment.downloads
    assert_empty @provider.llm_calls
  end

  def test_downloaded_size_is_rechecked_before_llm_even_if_blob_size_was_wrong
    @attachment.declared_size = 10
    @attachment.bytes = "x" * (3 * 1024 * 1024 + 1)

    assert_error(@provider.analyze_file(file_id: 42), /size limit/)
    assert_equal 1, @attachment.downloads
    assert_empty @provider.llm_calls
  end

  def test_nonpositive_attachment_limit_blocks_transmission
    AiHelperSetting.attachment_max_size_mb = 0

    assert_error(@provider.analyze_file(file_id: 42), /size limit/)
    assert_equal 0, @attachment.downloads
    assert_empty @provider.llm_calls
  end

  def test_missing_attachment_is_rejected_without_download
    @attachment.attached = false

    assert_error(@provider.analyze_file(file_id: 42), /no attached file/)
    assert_equal 0, @attachment.downloads
    assert_empty @provider.llm_calls
  end

  def test_unsupported_office_documents_are_rejected_without_download
    @file.name = "spec.docx"

    assert_error(@provider.analyze_file(file_id: 42), /not supported/)
    assert_equal 0, @attachment.downloads
    assert_empty @provider.llm_calls
  end

  def test_invalid_utf8_text_is_rejected_before_llm
    @file.name = "spec.txt"
    @attachment.bytes = "\xFF\xFE".b

    assert_error(@provider.analyze_file(file_id: 42), /UTF-8/)
    assert_equal 1, @attachment.downloads
    assert_empty @provider.llm_calls
  end

  def test_valid_utf8_text_is_accepted
    @file.name = "spec.txt"
    @attachment.bytes = "Specifiche del progetto: qualità".b

    refute @provider.analyze_file(file_id: 42).key?(:error)
    assert_equal 1, @provider.llm_calls.length
  end

  def test_invalid_questions_are_rejected_before_storage_access
    [42, false, "x" * 2_001].each do |question|
      assert_error(@provider.analyze_file(file_id: 42, question: question), /question/)
    end
    assert_no_document_read
  end

  private

  def ids(result)
    refute result.key?(:error), "Unexpected tool error: #{result.inspect}"
    result.fetch(:documents).map { |document| document.fetch(:id) }
  end

  def assert_error(result, message)
    assert_kind_of Hash, result
    assert_match message, result.fetch(:error)
  end

  def assert_no_document_read
    assert_equal 0, @revision.file_reads
    assert_equal 0, @attachment.downloads
    assert_empty @provider.llm_calls
  end

  def make_matching_files(count)
    DmsfFile.records = Array.new(count) do |index|
      DmsfFile.new(42 + index, project: @project, revision: @revision)
    end
  end
end
