import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class AdminLessonEditorScreen extends StatefulWidget {
  const AdminLessonEditorScreen({super.key});

  @override
  State<AdminLessonEditorScreen> createState() => _AdminLessonEditorScreenState();
}

class _AdminLessonEditorScreenState extends State<AdminLessonEditorScreen> {
  final _formKey = GlobalKey<FormState>();
  final _titleController = TextEditingController();
  final _categoryController = TextEditingController(text: 'Beginner');
  final _descriptionController = TextEditingController();
  final _videoUrlController = TextEditingController();
  final _thumbnailController = TextEditingController();
  bool _saving = false;

  @override
  void dispose() {
    _titleController.dispose();
    _categoryController.dispose();
    _descriptionController.dispose();
    _videoUrlController.dispose();
    _thumbnailController.dispose();
    super.dispose();
  }

  Future<void> _saveLesson() async {
    if (!_formKey.currentState!.validate()) return;

    setState(() => _saving = true);
    try {
      await Supabase.instance.client.from('lessons').insert({
        'title': _titleController.text.trim(),
        'category': _categoryController.text.trim(),
        'description': _descriptionController.text.trim(),
        'video_url': _videoUrlController.text.trim().isEmpty ? null : _videoUrlController.text.trim(),
        'thumbnail': _thumbnailController.text.trim().isEmpty ? null : _thumbnailController.text.trim(),
      });

      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Lesson published successfully')),
      );
      _formKey.currentState!.reset();
      _titleController.clear();
      _categoryController.text = 'Beginner';
      _descriptionController.clear();
      _videoUrlController.clear();
      _thumbnailController.clear();
      FocusScope.of(context).unfocus();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to publish lesson: $e')),
      );
    } finally {
      if (mounted) {
        setState(() => _saving = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Admin Lesson Publisher')),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            const Text(
              'Publish lessons here and they will appear automatically in the user Learn Trading section.',
              style: TextStyle(color: Colors.white70),
            ),
            const SizedBox(height: 16),
            TextFormField(
              controller: _titleController,
              decoration: const InputDecoration(labelText: 'Lesson Title'),
              validator: (value) => (value == null || value.trim().isEmpty) ? 'Title is required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _categoryController,
              decoration: const InputDecoration(labelText: 'Category'),
              validator: (value) => (value == null || value.trim().isEmpty) ? 'Category is required' : null,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _descriptionController,
              decoration: const InputDecoration(labelText: 'Description'),
              minLines: 4,
              maxLines: 6,
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _videoUrlController,
              decoration: const InputDecoration(labelText: 'Video URL (optional)'),
            ),
            const SizedBox(height: 12),
            TextFormField(
              controller: _thumbnailController,
              decoration: const InputDecoration(labelText: 'Thumbnail URL (optional)'),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _saving ? null : _saveLesson,
              icon: _saving
                  ? const SizedBox(
                      width: 18,
                      height: 18,
                      child: CircularProgressIndicator(strokeWidth: 2),
                    )
                  : const Icon(Icons.publish_outlined),
              label: Text(_saving ? 'Publishing...' : 'Publish Lesson'),
            ),
          ],
        ),
      ),
    );
  }
}
