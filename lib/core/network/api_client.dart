import 'package:dio/dio.dart';
import 'package:trademind_ai/core/config/app_config.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

class ApiClient {
  ApiClient({String? baseUrl})
      : dio = Dio(
          BaseOptions(
            baseUrl: baseUrl ?? AppConfig.apiBaseUrl,
            connectTimeout: const Duration(seconds: 60),
            receiveTimeout: const Duration(seconds: 60),
            sendTimeout: const Duration(seconds: 60),
            responseType: ResponseType.json,
            headers: const {
              'Content-Type': 'application/json',
              'Accept': 'application/json',
            },
          ),
        ) {
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          final session = Supabase.instance.client.auth.currentSession;
          final token = session?.accessToken;
          if (token != null && token.isNotEmpty) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
  }

  final Dio dio;

  Future<dynamic> get(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.get(path, queryParameters: queryParameters, options: options);
  }

  Future<Response<dynamic>> post(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.post(path, data: data, queryParameters: queryParameters, options: options);
  }

  Future<Response<dynamic>> patch(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.patch(path, data: data, queryParameters: queryParameters, options: options);
  }

  Future<Response<dynamic>> put(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.put(path, data: data, queryParameters: queryParameters, options: options);
  }

  Future<Response<dynamic>> delete(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
  }) {
    return dio.delete(path, data: data, queryParameters: queryParameters, options: options);
  }
}
