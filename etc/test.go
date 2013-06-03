
# Used to see how the mime/multipart parser works

package main;

import (
    "mime/multipart"
    "log"
    "os"
)


func main() {
	boundary := "----------------------------3518f3245f47"

	file, err := os.Open("test_data.dat")
	if (err != nil) {
		log.Fatal(err)
	}
	pizza := multipart.NewReader(file, boundary)

	part, _ := pizza.NextPart()
	part2, _ := pizza.NextPart()
	log.Print(part)
	log.Print(part2.FileName())

	bytes := make([]byte, 1024)
	ret, _ := part2.Read(bytes)

	log.Print(string(bytes))
	log.Print(ret)
}
