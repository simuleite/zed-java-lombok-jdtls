package com.example.testlombok.service;

import com.example.testlombok.entity.User;
import org.springframework.stereotype.Service;

@Service
public class UserService {

    public User createDemoUser() {
        User user = new User();
        user.setId(1L);
        user.setUsername("test");
        user.setEmail("test@example.com");
        user.setAge(25);

        // 测试 Lombok 生成的 toString 方法
        System.out.println("Created user: " + user.toString());

        // 测试 Lombok 生成的 getter 方法
        System.out.println("Username: " + user.getUsername());

        return user;
    }
}
